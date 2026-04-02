# PARWA Feature Catalog v1.0

> **AI-Powered Customer Support Platform — 500+ Features**
>
> This document catalogs every feature in the PARWA platform, organized by functional domain. Each feature includes its unique identifier, a one-line description, the technical area it belongs to, the applicable Building Codes (BC-001 through BC-012), its implementation priority, and dependencies on other features.
>
> **Building Codes Reference:**

| Code | Name |
|------|------|
| BC-001 | Multi-Tenant Isolation |
| BC-002 | Financial Actions |
| BC-003 | Webhook Handling |
| BC-004 | Background Jobs (Celery) |
| BC-005 | Real-Time Communication (Socket.io) |
| BC-006 | Email Communication (Brevo) |
| BC-007 | AI Model Interaction (Smart Router) |
| BC-008 | State Management (GSD Engine) |
| BC-009 | Approval Workflow (Approve/Reject) |
| BC-010 | Data Lifecycle & Compliance (GDPR) |
| BC-011 | Authentication & Security |
| BC-012 | Error Handling & Resilience |

---

## Table of Contents

1. [Category 1: Public Facing (Discovery & Conversion)](#category-1-public-facing-discovery--conversion) — F-001 to F-009
2. [Category 2: Authentication & Security](#category-2-authentication--security) — F-010 to F-019
3. [Category 3: Billing & Payments (Paddle)](#category-3-billing--payments-paddle) — F-020 to F-027
4. [Category 4: Onboarding](#category-4-onboarding) — F-028 to F-035
5. [Category 5: Dashboard](#category-5-dashboard) — F-036 to F-045
6. [Category 6: Ticket Management](#category-6-ticket-management) — F-046 to F-052

---

## Category 1: Public Facing (Discovery & Conversion)

The Public Facing category encompasses all visitor-facing features designed to attract, engage, and convert prospects into paying customers. These features form the top of the PARWA marketing funnel — from the initial landing experience through interactive demos, pricing transparency, and lead capture mechanisms.

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-001 | Landing Page with Industry Selector | A dynamic, conversion-optimized landing page presenting PARWA's value proposition with a dropdown industry selector that tailors content, testimonials, and use-case examples to the visitor's vertical (e.g., e-commerce, SaaS, healthcare). | Frontend | BC-001, BC-012 | Medium | — |
| F-002 | Dogfooding Banner | A prominent banner displayed at the top of the public site announcing that PARWA's own customer support is powered by PARWA — serving as a live proof-of-concept and credibility signal to prospective buyers evaluating platform quality. | Frontend | BC-012 | Low | F-001 |
| F-003 | Live AI Demo Widget (Chat) | An embedded chat widget on public pages that lets visitors interact directly with a live PARWA AI agent, demonstrating natural language understanding, response quality, and conversation flow without requiring any sign-up or commitment. | Frontend, AI | BC-007, BC-005, BC-012 | High | F-001 |
| F-004 | Pricing Page with Variant Cards | A dedicated pricing page displaying three subscription tier cards — Starter ($999/mo), Growth ($2,499/mo), and High ($3,999/mo) — each with a detailed feature comparison matrix, toggle for annual billing discounts, and a CTA to start a free trial. | Frontend | BC-001, BC-002, BC-012 | Critical | F-001 |
| F-005 | Smart Bundle Visualizer | An interactive tool on the pricing page that allows prospects to dynamically build a custom bundle by toggling add-on modules (e.g., voice support, SMS, advanced analytics), instantly recalculating the total monthly cost in real time. | Frontend, Backend | BC-001, BC-002, BC-012 | Medium | F-004 |
| F-006 | Anti-Arbitrage Matrix | A backend-driven pricing intelligence module that detects and prevents users from gaming the subscription tiers by comparing ticket volumes, usage patterns, and plan selection — surfacing upgrade nudges or overage projections before abuse occurs. | Backend, Frontend | BC-002, BC-001, BC-012 | High | F-004 |
| F-007 | ROI Calculator | An interactive calculator widget where prospects input their current support metrics (headcount, avg. ticket cost, volume) and receive a personalized projected ROI breakdown showing estimated monthly and annual savings from adopting PARWA. | Frontend, Backend | BC-001, BC-012 | High | F-001 |
| F-008 | Voice Demo Paywall ($1) | A gated demo experience where visitors can test PARWA's voice AI capabilities by paying a nominal $1 fee via Stripe, reducing free-demo abuse while giving serious buyers a hands-on preview of telephony features and voice quality. | Frontend, Backend | BC-002, BC-012 | Medium | F-003 |
| F-009 | Newsletter Subscription (Footer) | A footer-embedded email capture form integrated with Brevo that collects prospect email addresses for marketing drip campaigns, product updates, and event invitations, with double opt-in compliance and preference management. | Frontend, Backend | BC-006, BC-010, BC-012 | Low | F-001 |

> **Note:** Category 1 features are primarily visitor-facing and have minimal cross-feature dependencies. They serve as the entry point to the PARWA ecosystem and feed directly into the authentication and billing flows. Most features here are Frontend-heavy, with select features requiring Backend support for dynamic pricing logic and email integration.

---

## Category 2: Authentication & Security

The Authentication & Security category covers the complete identity lifecycle — from registration and login through multi-factor authentication, session governance, and programmatic API access. These features form the security perimeter of the platform and are foundational to every subsequent authenticated experience.

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-010 | User Registration (Email + Password) | A secure registration flow collecting email, password (with strength validation), company name, and role — creating a tenant-scoped user account with email uniqueness enforcement, password hashing via bcrypt, and initial verification state tracking. | Frontend, Backend | BC-011, BC-010, BC-001, BC-012 | Critical | — |
| F-011 | Google OAuth Login | A single sign-on integration with Google Identity Services allowing users to register or log in using their corporate Google account, auto-populating profile fields and supporting both personal and organizational Google accounts with domain verification. | Frontend, Backend | BC-011, BC-012 | High | F-010 |
| F-012 | Email Verification | An automated verification flow that sends a time-limited, single-use confirmation link to newly registered users via Brevo, blocking access to all authenticated features until the email is verified, with resend capability and token expiration handling. | Backend, Frontend | BC-006, BC-011, BC-012, BC-004 | Critical | F-010 |
| F-013 | Login System | The primary authentication endpoint accepting email/password credentials with rate-limited attempts, credential validation against hashed storage, JWT token issuance (access + refresh), and secure cookie-based session establishment with HTTP-only and SameSite flags. | Frontend, Backend | BC-011, BC-012, BC-001 | Critical | F-010, F-012 |
| F-014 | Forgot Password / Reset Password | A self-service password recovery flow that accepts a registered email, sends a secure reset link with a time-limited token via Brevo, and allows the user to set a new password through a verified form — invalidating all existing sessions upon reset. | Frontend, Backend | BC-006, BC-011, BC-012 | High | F-013 |
| F-015 | MFA Setup (Authenticator App) | A two-factor authentication enrollment flow that guides users through linking a TOTP-compatible authenticator app (e.g., Google Authenticator, Authy) by displaying a QR code and verifying a generated code before activating MFA on their account. | Frontend, Backend | BC-011, BC-012 | High | F-013 |
| F-016 | Backup Codes Generation | Upon MFA activation, the system generates and displays a set of single-use backup recovery codes that the user must securely store — each code can be used exactly once to bypass MFA if the authenticator device is lost or inaccessible. | Backend, Frontend | BC-011, BC-012 | High | F-015 |
| F-017 | Session Management (Active Sessions, Revoke) | A session governance interface allowing authenticated users to view all currently active sessions across devices and browsers, with the ability to selectively revoke individual sessions or terminate all other sessions for security purposes. | Backend, Frontend | BC-011, BC-012, BC-001 | High | F-013 |
| F-018 | Rate Limiting (Advanced, Per-User) | A sophisticated, per-user rate limiting system that enforces configurable thresholds on authentication endpoints (login, password reset, registration) and API calls — using sliding window algorithms with progressive backoff and automatic temporary lockouts. | Backend | BC-011, BC-012 | High | F-013 |
| F-019 | API Key Management (Client API Keys) | A key lifecycle management module enabling tenants to create, rotate, and revoke API keys for programmatic access to the PARWA API — each key carries metadata (name, permissions, expiration) and all key usage is audit-logged per tenant. | Backend, Frontend | BC-011, BC-012, BC-001 | High | F-017 |

> **Note:** Category 2 features are the security backbone of PARWA. Nearly every authenticated feature downstream depends on F-013 (Login System). MFA (F-015, F-016) and rate limiting (F-018) are essential for enterprise-grade security posture. API Key Management (F-019) bridges authentication with external integrations and custom integration builders.

---

## Category 3: Billing & Payments (Paddle)

The Billing & Payments category manages the entire monetization lifecycle through Paddle — from checkout and subscription management to invoicing, overage handling, and cancellation flows. Financial accuracy, webhook reliability, and graceful user experiences during plan changes are critical here.

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-020 | Paddle Checkout Integration | A tightly integrated checkout experience using Paddle's overlay or custom checkout that initiates subscription purchases from the pricing page, passing plan IDs, tenant metadata, and custom attributes — handling tax calculations and localization automatically. | Frontend, Backend | BC-002, BC-003, BC-012, BC-001 | Critical | F-004 |
| F-021 | Subscription Management (Upgrade/Downgrade) | A self-service subscription management interface allowing tenants to switch between Starter, Growth, and High plans — with prorated billing calculations, immediate or next-cycle生效 options, and feature entitlement updates upon plan change confirmation. | Frontend, Backend | BC-002, BC-003, BC-009, BC-012 | High | F-020 |
| F-022 | Paddle Webhook Handler (All Events) | A comprehensive, idempotent webhook receiver that processes all Paddle event types (subscription.created, payment.succeeded, payment.failed, subscription.cancelled, etc.) — validating signatures, deduplicating events, and triggering appropriate downstream actions. | Backend | BC-003, BC-002, BC-012, BC-004 | Critical | F-020 |
| F-023 | Invoice History | A paginated, searchable list of all invoices associated with a tenant's account — pulled from Paddle and enriched with local metadata — allowing users to view, download PDF copies, and track payment status for each billing period. | Frontend, Backend | BC-002, BC-001, BC-012 | High | F-022 |
| F-024 | Daily Overage Charging ($0.10/ticket) | A daily cron job that calculates ticket volumes exceeding each tenant's plan inclusion threshold, generates prorated overage charges at $0.10 per additional ticket, and submits the charge to Paddle — with email notification and dashboard visibility. | Backend | BC-002, BC-004, BC-012, BC-006, BC-001 | High | F-022, F-046 |
| F-025 | Graceful Cancellation Flow (Multi-option) | A multi-step cancellation experience that presents departing users with retention options (pause, downgrade, discount offer) before confirming cancellation — capturing cancellation reasons and feedback to inform product improvements and reduce churn. | Frontend, Backend | BC-002, BC-009, BC-012, BC-001 | High | F-021 |
| F-026 | Cancellation Request Tracking | A backend tracking system that logs all cancellation requests, their stated reasons, retention offers made, and final outcomes — providing the product and success teams with an analytics-ready dataset for churn analysis and win-back campaign targeting. | Backend, Frontend | BC-002, BC-001, BC-009, BC-012 | Medium | F-025 |
| F-027 | Payment Confirmation & Verification | A post-checkout verification flow that confirms successful payment processing with Paddle, updates tenant entitlements and plan status in the local database, sends a welcome/confirmation email via Brevo, and redirects the user to the onboarding wizard. | Backend, Frontend | BC-002, BC-003, BC-012, BC-006, BC-001 | Critical | F-020 |

> **Note:** Category 3 is entirely dependent on the Paddle payment platform. The Webhook Handler (F-022) is the single most critical backend feature here — every financial state change flows through it. Overage charging (F-024) bridges billing with ticket management data. The cancellation flow (F-025) directly impacts retention metrics and requires careful UX design with approval workflow patterns.

---

## Category 4: Onboarding

The Onboarding category guides new customers from their first authenticated moment through full platform activation — including legal consent, integration setup, knowledge base ingestion, and AI readiness. The goal is to deliver a "First Victory" as fast as possible.

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-028 | Onboarding Wizard (5-Step) | A guided, multi-step onboarding wizard that walks new users through platform configuration in five sequential stages — company profile, legal consent, integration setup, knowledge base upload, and AI activation — with progress tracking and the ability to save and resume. | Frontend, Backend | BC-008, BC-012, BC-001 | High | F-013 |
| F-029 | Legal Consent Collection (TCPA, GDPR, Call Recording) | A consent management step within onboarding that presents and collects explicit opt-in for TCPA compliance, GDPR data processing agreement, and call recording permissions — storing signed consent records with timestamps and IP addresses for audit readiness. | Frontend, Backend | BC-010, BC-009, BC-001, BC-012 | Critical | F-028 |
| F-030 | Pre-built Integration Setup | A selection interface offering one-click configuration of pre-built integrations with popular platforms (Zendesk, Freshdesk, Intercom, Slack, Shopify, etc.) — each with guided OAuth or API key authorization flows and automatic data sync scheduling. | Frontend, Backend | BC-003, BC-004, BC-001, BC-012 | High | F-028 |
| F-031 | Custom Integration Builder (REST/GraphQL/Webhook/DB) | An advanced integration configuration tool enabling users to define custom data connections using REST APIs, GraphQL endpoints, incoming/outgoing webhooks, or direct database connections — with request/response mapping, authentication setup, and test connectivity validation. | Frontend, Backend | BC-003, BC-004, BC-001, BC-012 | High | F-030 |
| F-032 | Knowledge Base Document Upload | A document ingestion interface supporting drag-and-drop upload of knowledge base materials in multiple formats (PDF, DOCX, TXT, Markdown, HTML, CSV) — with chunking previews, duplicate detection, and upload progress tracking per document. | Frontend, Backend | BC-004, BC-001, BC-012 | High | F-028 |
| F-033 | Knowledge Base Processing & Indexing | A background processing pipeline (Celery) that ingests uploaded documents, performs text extraction, chunking, embedding generation, and vector indexing — storing results in a tenant-isolated vector database with progress status reporting and error recovery. | Backend, AI | BC-004, BC-007, BC-001, BC-012 | Critical | F-032 |
| F-034 | AI Activation System | The final onboarding gate that validates all prerequisites (consent collected, at least one integration active, knowledge base indexed) and activates the tenant's AI agent — performing a readiness check, configuring the Smart Router, and enabling live ticket processing. | Backend, AI | BC-007, BC-008, BC-001, BC-012 | Critical | F-033, F-029, F-030 |
| F-035 | First Victory Celebration | A celebratory modal and confetti animation displayed when a tenant's AI agent successfully resolves its first customer ticket — marking the milestone in the activity feed and triggering a congratulatory email to the account owner. | Frontend | BC-012, BC-006, BC-005 | Medium | F-034 |

> **Note:** Category 4 is the critical path from sign-up to value realization. The onboarding wizard (F-028) orchestrates the entire flow. Legal consent (F-029) must be completed before any data processing begins. Knowledge Base Processing (F-033) is the heaviest background operation and directly gates AI Activation (F-034). The First Victory (F-035) is the emotional peak of the onboarding experience and a key retention signal.

---

## Category 5: Dashboard

The Dashboard category provides the command center for PARWA users — offering real-time operational visibility, financial metrics, adaptation insights, and proactive recommendations. These features transform raw platform data into actionable intelligence.

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-036 | Dashboard Home Overview | The primary dashboard landing page presenting a unified, card-based layout of all key widgets — activity feed, metrics summary, adaptation tracker, savings counter, and contextual alerts — personalized to the tenant's role and plan tier. | Frontend, Backend | BC-001, BC-012, BC-011 | High | F-013 |
| F-037 | Activity Feed (Real-time) | A live-updating activity stream showing recent platform events — new tickets, AI resolutions, escalations, integration syncs, and team actions — delivered via Socket.io with pagination, filtering by event type, and link-through to relevant detail views. | Frontend, Backend | BC-005, BC-001, BC-012 | High | F-036 |
| F-038 | Key Metrics Overview | A widget grid displaying the tenant's most important KPIs — total tickets, AI resolution rate, avg. response time, customer satisfaction score, and active integration health — with configurable time ranges (24h, 7d, 30d) and trend sparklines. | Frontend, Backend | BC-001, BC-012, BC-007 | High | F-036 |
| F-039 | Adaptation Tracker (Day X/30) | A visual progress indicator showing how far into the 30-day AI adaptation period the tenant currently is — displaying improvement trends for AI accuracy, resolution rate, and customer satisfaction as the system learns from the tenant's data over time. | Frontend, Backend | BC-001, BC-008, BC-012 | Medium | F-034, F-036 |
| F-040 | Running Total Widget (Cumulative Savings) | A prominently displayed financial widget that continuously calculates and displays the cumulative cost savings achieved by PARWA's AI automation — comparing actual AI-resolved ticket costs against estimated human-agent costs with a running dollar total. | Frontend, Backend | BC-001, BC-002, BC-012 | Medium | F-038 |
| F-041 | Workforce Allocation Map | A visual breakdown showing how the tenant's support workforce is distributed between AI-resolved tickets and human-handled tickets — presented as a pie or bar chart with drill-down by category, channel, and time period. | Frontend, Backend | BC-001, BC-012 | Medium | F-038 |
| F-042 | Growth Nudge Alert | A proactive notification widget that analyzes usage patterns and alerts the tenant when they are approaching plan limits, experiencing rapid growth that may warrant an upgrade, or underutilizing features they've already paid for. | Frontend, Backend | BC-006, BC-001, BC-012, BC-005 | Medium | F-038 |
| F-043 | Feature Discovery Teaser | A rotating banner or tooltip system on the dashboard that highlights underused or newly released features — driving feature adoption by surfacing contextual suggestions based on the tenant's current configuration and usage patterns. | Frontend, Backend | BC-001, BC-012 | Low | F-036 |
| F-044 | Seasonal Spike Forecast | An AI-powered predictive widget that forecasts upcoming support volume spikes based on historical patterns, seasonal trends, and business calendar events — recommending proactive staffing or AI capacity adjustments before demand surges hit. | Frontend, AI, Backend | BC-007, BC-001, BC-012 | Medium | F-034, F-038 |
| F-045 | Contextual Help System | An in-app help overlay that provides relevant documentation, video tutorials, and support contact options based on the user's current location within the platform — reducing friction and support requests through self-service guidance. | Frontend | BC-012, BC-001 | Low | F-036 |

> **Note:** Category 5 features are highly interdependent — nearly all dashboard widgets build on F-036 (Dashboard Home) as their container and F-038 (Key Metrics) as their primary data source. Real-time features like the Activity Feed (F-037) require Socket.io infrastructure. AI-powered features like Seasonal Spike Forecast (F-044) depend on sufficient platform usage data to generate meaningful predictions.

---

## Category 6: Ticket Management

The Ticket Management category is the operational core of PARWA — handling the complete lifecycle of customer support tickets from creation through classification, assignment, and resolution across multiple channels. These features directly enable AI-powered support automation.

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-046 | Ticket List (Filterable, Sortable) | The primary ticket management view presenting a paginated, multi-column list of all support tickets — with filtering by status, channel, assignee, priority, and date range, plus sorting by any column and quick-view preview on row hover. | Frontend, Backend | BC-001, BC-012, BC-011 | Critical | F-036 |
| F-047 | Ticket Detail Modal (Full Conversation) | A slide-in or modal detail view showing the complete conversation history for a selected ticket — including all messages (customer and agent/AI), metadata (channel, timestamps, classification), attached files, internal notes, and real-time status updates. | Frontend, Backend | BC-001, BC-005, BC-012 | Critical | F-046 |
| F-048 | Ticket Search (By Customer, ID, Content) | A powerful, full-text search interface allowing users to find tickets by customer name/email, ticket ID, or message content — with fuzzy matching, relevance ranking, and faceted filtering to narrow results across large ticket volumes. | Frontend, Backend | BC-001, BC-007, BC-012 | High | F-046 |
| F-049 | Ticket Classification (AI - Intent/Type) | An AI-driven classification engine that automatically categorizes every incoming ticket by intent (refund, technical support, billing, feature request, complaint) and type (urgent, routine, informational) using the Smart Router — enabling prioritized routing and response templating. | Backend, AI | BC-007, BC-001, BC-004, BC-012 | High | F-046, F-034 |
| F-050 | Ticket Assignment (Auto + Manual) | A flexible assignment system combining AI-powered automatic routing (based on classification, agent workload, and skill matching) with manual override capability — allowing supervisors to reassign tickets, set round-robin rules, and configure escalation paths. | Backend, Frontend | BC-001, BC-008, BC-012, BC-005 | High | F-046 |
| F-051 | Ticket Bulk Actions | A multi-select toolbar enabling users to perform batch operations on multiple tickets simultaneously — including status changes, reassignment, tagging, merging, exporting, and closing — with confirmation dialogs and undo capability for safety. | Frontend, Backend | BC-001, BC-012, BC-009 | Medium | F-046 |
| F-052 | Omnichannel Sessions (Email/Chat/SMS/Voice/Social) | A unified conversation view that consolidates all customer interactions across channels (email, live chat, SMS, voice calls, social media) into a single ticket thread — maintaining channel context while presenting a seamless, chronological conversation timeline. | Frontend, Backend, AI | BC-005, BC-007, BC-001, BC-012, BC-003 | High | F-046, F-030 |

> **Note:** Category 6 is the operational heart of PARWA. The Ticket List (F-046) is the entry point for all ticket operations and is one of the most performance-sensitive views in the application. AI Classification (F-049) is what makes PARWA intelligent — it requires a well-trained model and sufficient knowledge base data. Omnichannel Sessions (F-052) represents the most architecturally complex feature, requiring integration with multiple external channel providers and real-time message stitching. Bulk Actions (F-051) need approval workflow patterns for destructive operations.

---

## Summary Statistics (Part 1)

| Metric | Value |
|--------|-------|
| **Total Features (Part 1)** | 52 |
| **Categories** | 6 |
| **Critical Priority** | 14 |
| **High Priority** | 26 |
| **Medium Priority** | 10 |
| **Low Priority** | 2 |
| **Most Referenced Building Code** | BC-012 (Error Handling & Resilience) — 51 features |
| **Second Most Referenced** | BC-001 (Multi-Tenant Isolation) — 45 features |
| **Feature with Most Dependencies** | F-034 (AI Activation System) — 3 upstream dependencies |
| **Most Dependented Feature** | F-013 (Login System) — 6 downstream dependents |

## Category 7: AI Core Engine

> **The heart of PARWA.** This category contains 170+ sub-features in production — including individual prompt templates, model-specific fallback paths, edge-case handlers, per-intent logic branches, token-budget managers, and retrieval-rewrite-rerank pipelines. The 21 features listed below are the **major subsystems** that house those sub-features. Each will be expanded into its own Feature Spec document with full sub-feature breakdowns.

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-053 | GSD State Engine | Orchestrates structured, step-by-step state transitions for every support ticket from intake through resolution, persisting state across LLM calls and human handoffs | All | BC-008, BC-007 | **Critical** | F-060, F-054, F-059 |
| F-054 | Smart Router (3-Tier LLM) | Classifies incoming request complexity and routes to the optimal LLM tier — lightweight for FAQ, medium for reasoning, heavy for edge cases | AI / Backend | BC-007, BC-012 | **Critical** | F-059, F-062, F-055 |
| F-055 | Model Failover & Rate Limit Handling | Automatically detects rate limits, timeouts, and degraded model responses, then falls through to backup providers without dropping conversations | AI / Infra | BC-007, BC-012, BC-004 | **Critical** | F-054, F-093 |
| F-056 | PII Redaction Engine | Scans all incoming and outgoing text for PII (SSN, credit cards, emails, phones) and redacts before storage or LLM submission | AI / Backend | BC-007, BC-010, BC-011 | **Critical** | F-065, F-064 |
| F-057 | Guardrails AI (Content Safety) | Multi-layer content safety system that blocks harmful, off-topic, hallucinated, or policy-violating AI responses before they reach customers | AI | BC-007, BC-010, BC-009 | **Critical** | F-058, F-056, F-059 |
| F-058 | Blocked Response Manager & Review Queue | Captures all guardrail-blocked responses into a dedicated review queue where admins can inspect, edit, approve, or permanently ban patterns | Frontend / Backend | BC-007, BC-009, BC-010 | **High** | F-057, F-074, F-080 |
| F-059 | Confidence Scoring System | Assigns calibrated 0–100 confidence scores to every AI response based on retrieval relevance, intent match, historical accuracy, and context completeness | AI | BC-007, BC-008 | **Critical** | F-054, F-079, F-068 |
| F-060 | LangGraph Workflow Engine | Graph-based orchestration framework defining complex multi-step AI workflows as directed state machines with conditional branching and human checkpoints | AI / Backend | BC-007, BC-008, BC-004 | **Critical** | F-053, F-054, F-065 |
| F-061 | DSPy Prompt Optimization | Automated prompt engineering pipeline using DSPy to iteratively optimize prompt templates against historical resolution quality metrics | AI | BC-007, BC-004 | **High** | F-064, F-098, F-116 |
| F-062 | Ticket Intent Classification | Multi-label classifier categorizing tickets by intent (refund, technical, billing, complaint, feature request) to drive routing and response strategy | AI / Backend | BC-007, BC-008 | **High** | F-054, F-071, F-065 |
| F-063 | Sentiment Analysis (Empathy Engine) | Real-time sentiment detection scoring customer frustration levels and adjusting AI tone, escalation triggers, and notifications accordingly | AI | BC-007, BC-005 | **Medium** | F-054, F-080, F-065 |
| F-064 | Knowledge Base RAG (Vector Search) | RAG pipeline indexing knowledge articles into vector embeddings, performing semantic search, and feeding relevant context to the LLM for grounded responses | AI / Backend | BC-007, BC-010 | **Critical** | F-056, F-065, F-061 |
| F-065 | Auto-Response Generation | End-to-end pipeline combining intent classification, RAG retrieval, and template generation to produce brand-aligned customer responses automatically | AI | BC-007, BC-006, BC-005 | **High** | F-062, F-064, F-057, F-059 |
| F-066 | AI Draft Composer (Co-Pilot Mode) | Suggests response drafts to human agents in real-time for accept/edit/regenerate — reduces handle time while maintaining quality control | AI / Frontend | BC-007, BC-005 | **High** | F-064, F-059, F-063 |
| F-067 | Context Compression Trigger | Monitors token usage within conversations and compresses prior context when approaching context window limits to maintain coherence | AI | BC-007, BC-008 | **Medium** | F-053, F-068, F-054 |
| F-068 | Context Health Meter | Real-time dashboard indicator showing conversation context quality — warns when context is degraded, missing, or stale | AI / Frontend | BC-007, BC-008, BC-005 | **High** | F-059, F-067, F-053 |
| F-069 | 90% Capacity Popup (New Chat Trigger) | Proactive UI notification when conversation reaches 90% AI context capacity, prompting agent to start a fresh thread for new topics | Frontend | BC-005, BC-008 | **High** | F-068, F-067 |
| F-070 | Customer Identity Resolution (Cross-Channel) | Unifies customer identities across email, chat, phone, and social by matching on email, phone, account ID, and behavioral signals | AI / Backend | BC-001, BC-007, BC-010, BC-011 | **High** | F-062, F-130, F-056 |
| F-071 | Semantic Clustering (Batch Grouping) | Groups similar tickets using embedding-based similarity clustering for batch approval, bulk resolution, and trend identification | AI / Backend | BC-007, BC-004 | **Medium** | F-062, F-075, F-116 |
| F-072 | Subscription Change Proration | Calculates and applies prorated charges/credits when subscriptions are upgraded, downgraded, or cancelled mid-cycle | Backend | BC-002, BC-001 | **High** | F-062, F-099 |
| F-073 | Temporary Agent Expiry & Deprovisioning | Auto-deprovisions temporary agents when access period expires, revoking permissions and reassigning open tickets | Backend | BC-002, BC-004, BC-011 | **Medium** | F-097, F-099, F-011 |

> **Note:** The 21 features above represent the major subsystems. The AI Core Engine contains **150+ additional sub-features** including: per-intent prompt templates (≈40), model-specific response formatters (≈15), retrieval chunking strategies (≈8), reranking algorithms (≈5), hallucination detection patterns (≈12), edge-case handlers (≈20), token-budget managers (≈6), conversation summarization modes (≈4), and language detection/translation pipelines (≈8). Each major feature will have its own Feature Spec with full sub-feature decomposition.

---

## Category 8: Approval & Control System

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-074 | Approval Queue Dashboard | Centralized dashboard displaying all pending AI actions requiring human review, with filtering, sorting, search, and batch operations | Frontend / Backend | BC-009, BC-005 | **Critical** | F-059, F-057, F-076 |
| F-075 | Batch Approval (Semantic Clusters) | Allows supervisors to approve entire clusters of similar AI actions at once when semantic clustering confidence is above threshold | Frontend / Backend | BC-009, BC-007 | **High** | F-071, F-074, F-079 |
| F-076 | Individual Ticket Approval/Reject | Per-ticket review interface where supervisors read AI's proposed action, view confidence breakdown, and approve, reject, or edit | Frontend / Backend | BC-009, BC-002 | **Critical** | F-074, F-079, F-084 |
| F-077 | Auto-Handle Rules (Jarvis Consequence Display) | Configurable rules allowing AI to auto-handle specific actions without approval, with Jarvis previewing all consequences before activation | Backend / AI | BC-009, BC-002, BC-007 | **High** | F-087, F-088, F-074 |
| F-078 | Auto-Approve Confirmation Flow | When enabling auto-approve rules, Jarvis displays comprehensive multi-step confirmation showing every potential action, financial impact, and risk before user confirms | Frontend / AI | BC-009, BC-002, BC-011 | **Critical** | F-077, F-087, F-084 |
| F-079 | Confidence Score Breakdown | Visual drill-down of confidence showing individual component scores (retrieval, intent, sentiment, history) for transparency in decisions | Frontend / AI | BC-007, BC-009, BC-005 | **High** | F-059, F-076, F-074 |
| F-080 | Urgent Attention Panel (VIP/Legal) | Prominent UI panel flagging tickets from VIP customers and legal escalations — never auto-handled, always bubbles to top | Frontend / Backend | BC-009, BC-002, BC-011 | **Critical** | F-063, F-074, F-059 |
| F-081 | Approval Reminders (2h, 4h, 8h, 24h) | Escalating notifications reminding supervisors of pending approvals at 2h, 4h, 8h, and 24h intervals via in-app, email, and push | Backend / Frontend | BC-009, BC-005, BC-006, BC-004 | **High** | F-074, F-082 |
| F-082 | Approval Timeout (72h auto-reject) | Auto-rejects AI-suggested actions unreviewed for 72 hours, logging the timeout and triggering re-queuing if appropriate | Backend | BC-009, BC-004, BC-012 | **High** | F-074, F-081 |
| F-083 | Emergency Pause Controls | Kill-switch allowing admins to immediately pause AI auto-handling for all channels or specific channels in emergency situations | Frontend / Backend | BC-009, BC-011, BC-012 | **Critical** | F-054, F-087, F-057 |
| F-084 | Undo System (Action + Email Recall) | Reverses executed AI actions (refund reversal, status change) and recalls sent emails via Brevo API within the recall window | Backend | BC-009, BC-002, BC-006, BC-012 | **High** | F-076, F-120 |
| F-085 | Voice Confirmation (Mobile) | Mobile flow allowing supervisors to approve/reject tickets via voice commands with text-to-speech ticket summaries | Frontend / AI | BC-009, BC-005, BC-007, BC-011 | **Low** | F-074, F-076, F-127 |
| F-086 | Swipe Gestures (Mobile Approve/Reject) | Swipe-left (reject) and swipe-right (approve) gestures on mobile for rapid approval processing with haptic feedback | Frontend | BC-009, BC-005 | **Medium** | F-074, F-076 |

> **Note:** The Approval System follows **progressive autonomy** — as confidence rises and error rates drop, more actions move to auto-approve. The undo system (F-084) is the safety net making this approach viable.

---

## Category 9: Jarvis Command Center

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-087 | Jarvis Chat Panel (NL Commands) | Floating chat interface for natural language control — "show refund tickets," "pause email," "create returns agent" | AI / Frontend | BC-007, BC-005, BC-011 | **Critical** | F-054, F-053, F-088 |
| F-088 | System Status Panel | Real-time overview of all PARWA subsystem health — LLM status, queue depths, approval backlog, active agents, integration connectivity | Frontend / Backend | BC-005, BC-012 | **High** | F-137, F-055, F-091 |
| F-089 | GSD State Terminal | Live debugging terminal showing GSD state machine execution — active step, next step, pending decisions, and state variables | Frontend / Backend | BC-008, BC-005, BC-007 | **High** | F-053, F-060, F-087 |
| F-090 | Quick Command Buttons (Presets) | One-click preset buttons for common commands (pause all, export report, check health) alongside chat panel | Frontend | BC-005 | **Medium** | F-087, F-083 |
| F-091 | Last 5 Errors Panel | Persistent sidebar showing 5 most recent errors with stack traces, affected tickets, timestamps, and "investigate" links | Frontend / Backend | BC-012, BC-005 | **High** | F-088, F-092, F-093 |
| F-092 | Train from Error Button | One-click action packaging error context and ticket data into a training data point for model improvement | AI / Backend | BC-007, BC-004, BC-012 | **High** | F-091, F-100, F-103 |
| F-093 | Proactive Self-Healing | Continuously monitors external API calls for failures, auto-retrying with fallback strategies before alerting humans | Backend / Infra | BC-012, BC-004, BC-003 | **Critical** | F-055, F-137, F-139 |
| F-094 | Trust Preservation Protocol | When external systems fail, ensures PARWA never tells customer "we can't help" — queues actions and provides reassuring messaging | AI / Backend | BC-012, BC-007, BC-005 | **High** | F-093, F-054, F-065 |
| F-095 | Jarvis "Create Agent" Command | NL agent creation — "create a returns specialist" — guided setup flow provisioning new agent with permissions and training | AI / Frontend | BC-007, BC-001, BC-011 | **High** | F-087, F-097, F-099, F-100 |
| F-096 | Dynamic Instruction Workflow | Create, modify, and version-control instruction sets that AI agents follow, with A/B testing between variants | AI / Backend | BC-007, BC-008, BC-001 | **Medium** | F-087, F-060, F-061 |

> **Note:** Jarvis turns a complex multi-system AI platform into something controllable through conversation. The natural language layer (F-087) wraps every other system, and self-healing protocols (F-093, F-094) keep the system running even when components fail.

---

## Category 10: Agent Management & Training

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-097 | Agent Dashboard (Cards with Status) | Card-based dashboard showing all AI agents with status (active, training, paused), specialty, performance, and quick-action buttons | Frontend / Backend | BC-005, BC-001 | **High** | F-099, F-098 |
| F-098 | Agent Performance Metrics | Per-agent analytics: resolution rate, avg confidence, CSAT, escalation frequency, handling time — used for monitoring and training triggers | Backend / AI | BC-007, BC-001, BC-004 | **High** | F-097, F-100, F-101, F-109 |
| F-099 | Add/Scale Agent (Paddle Trigger) | Agent provisioning flow triggering Paddle checkout, then auto-provisioning with base training, permissions, and integration access | Frontend / Backend | BC-002, BC-001, BC-011 | **High** | F-097, F-100, F-020 |
| F-100 | Agent Lightning Training Loop | Rapid training pipeline taking new agent from baseline to production-ready using domain-specific data and transfer learning | AI / Backend | BC-007, BC-004 | **High** | F-099, F-103, F-104, F-105 |
| F-101 | 50-Mistake Threshold Trigger | Automatic training activation when agent accumulates 50 mistakes — packages error data, generates dataset, initiates retraining | AI / Backend | BC-007, BC-004, BC-012 | **High** | F-098, F-092, F-100, F-103 |
| F-102 | Training Run Execution (LOCAL) | Orchestrates training on local/cloud GPU (Colab/RunPod), managing data transfer, training loops, checkpointing, and result retrieval | AI / Infra | BC-007, BC-004 | **High** | F-100, F-103, F-104 |
| F-103 | Training Dataset Preparation | Automated pipeline cleaning, deduplicating, formatting, and validating training data from ticket histories and error logs | AI / Backend | BC-007, BC-004, BC-010 | **High** | F-092, F-101, F-102 |
| F-104 | Model Validation (Post-Training) | Evaluation suite testing retrained models against holdout datasets, edge-case scenarios, and regression tests before deployment | AI / Backend | BC-007, BC-012, BC-004 | **Critical** | F-102, F-105, F-116 |
| F-105 | Model Deployment with Auto-Rollback | Zero-downtime canary deployment auto-rolling back if quality metrics degrade below threshold | AI / Infra | BC-007, BC-012, BC-004 | **Critical** | F-104, F-055, F-098 |
| F-106 | Time-Based Fallback Training (Bi-weekly) | Scheduled retraining every 2 weeks regardless of mistake count, incorporating all new ticket data to prevent drift | AI / Backend | BC-007, BC-004 | **Medium** | F-100, F-103, F-104, F-116 |
| F-107 | Cold Start Problem Handler | Specialized onboarding for new agents with zero data — uses general knowledge, industry templates, and higher approval thresholds | AI / Backend | BC-001, BC-007, BC-009 | **High** | F-099, F-100, F-059 |
| F-108 | Peer Review (Junior asks Senior) | Lower-confidence agents escalate uncertain tickets to higher-performing "senior" agents before sending to humans | AI / Backend | BC-007, BC-008, BC-009 | **Medium** | F-059, F-097, F-074 |

> **Note:** The training pipeline (F-100 → F-105) is a **closed loop**: mistakes → dataset prep → training → validation → deployment → performance monitoring → next cycle. The 50-mistake threshold (F-101) and 2-week fallback (F-106) ensure both reactive and proactive activation.

---

## Category 11: Analytics & Reporting

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-109 | Analytics Overview Dashboard | Primary analytics hub showing ticket volume, resolution rate, AI vs human split, CSAT, and trend indicators | Frontend / Backend | BC-005, BC-001 | **High** | F-110, F-111, F-112, F-098 |
| F-110 | Time Range Selector | Date range picker (today, 7d, 30d, 90d, custom) filtering all dashboard widgets and reports | Frontend / Backend | BC-005 | **Medium** | F-109, F-111, F-112 |
| F-111 | Key Metrics Cards | Summary KPIs: total tickets, auto-resolved %, avg resolution time, CSAT, AI confidence avg, approval queue depth | Frontend / Backend | BC-005 | **High** | F-109, F-098, F-059 |
| F-112 | Trend Charts | Interactive line/bar charts showing ticket volume by channel, resolution rate progression, confidence evolution, escalation frequency | Frontend / Backend | BC-005 | **High** | F-109, F-110, F-115 |
| F-113 | ROI Dashboard | Financial impact: AI automation cost savings vs human handling, agent cost, time saved, projected annual savings | Frontend / Backend | BC-002, BC-005 | **High** | F-098, F-099, F-111 |
| F-114 | Performance Comparison (Before/After) | Side-by-side metrics before and after PARWA deployment or after specific configuration changes | Frontend / Backend | BC-005 | **Medium** | F-109, F-112, F-113 |
| F-115 | Confidence Trend Chart | Dedicated chart tracking AI confidence distribution and trends with anomaly highlighting below thresholds | Frontend / AI | BC-007, BC-005 | **High** | F-059, F-112, F-116 |
| F-116 | Drift Detection Report | Automated report detecting AI performance drift — increasing errors, shifting confidence, changing resolution patterns | AI / Backend | BC-007, BC-004, BC-012 | **High** | F-098, F-115, F-106, F-101 |
| F-117 | Analytics Data Export (CSV/PDF) | Export any dashboard view or report as CSV (raw data) or PDF (formatted) with scheduled export options | Frontend / Backend | BC-005, BC-010 | **Medium** | F-109, F-112, F-113 |
| F-118 | Quality Coach Reports (PARWA High) | AI-generated coaching insights analyzing agent performance patterns with specific improvement recommendations | AI / Frontend | BC-007, BC-005, BC-009 | **Medium** | F-098, F-116, F-119 |
| F-119 | Post-Interaction QA Rating | Automated QA scoring every resolved ticket on accuracy, tone, completeness, and compliance — feeds analytics and training | AI / Backend | BC-007, BC-004 | **High** | F-065, F-098, F-103, F-118 |

> **Note:** Analytics serves dual purposes: **operational visibility** (F-109–F-114) for management and **AI quality governance** (F-115–F-119) for model improvement. Drift detection (F-116) bridges analytics and the training loop.

---

## Category 12: Communication Channels

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-120 | Email Handling (Outbound via Brevo) | Outbound email delivery using Brevo API with template management, batch sending, delivery tracking, and reply threading | Backend | BC-006, BC-003, BC-004 | **Critical** | F-065, F-121, F-084 |
| F-121 | Inbound Email Parsing (Brevo Webhook) | Webhook receiver parsing incoming emails via Brevo Parse, extracting body, headers, attachments, and routing to tickets | Backend | BC-006, BC-003 | **Critical** | F-120, F-062, F-070 |
| F-122 | OOO/Auto-Reply Detection | Detects out-of-office and auto-reply messages preventing unnecessary ticket creation or AI responses | Backend / AI | BC-006, BC-007 | **Medium** | F-121, F-062 |
| F-123 | Email Rate Limiting (5/thread/24h) | Enforces max 5 outbound emails per thread per 24h to prevent spam behavior | Backend | BC-006, BC-012 | **High** | F-120, F-083 |
| F-124 | Bounce & Complaint Handling | Processes bounces and spam complaints, updating contact validity and pausing outbound for flagged addresses | Backend | BC-006, BC-012, BC-010 | **High** | F-120, F-010 |
| F-125 | Chat Widget (Live on Landing + Dashboard) | Embeddable chat widget: customer-facing on landing, internal agent chat within dashboard | Frontend / Backend | BC-005, BC-001, BC-011 | **High** | F-065, F-066, F-087 |
| F-126 | SMS Handling (Twilio) | Two-way SMS via Twilio for ticket notifications, follow-ups, and SMS-based support with opt-in compliance | Backend | BC-005, BC-010, BC-011 | **Medium** | F-070, F-083 |
| F-127 | Voice Call Handling (Twilio) | Twilio voice calls with IVR routing, call recording, and voicemail transcription | Backend / AI | BC-005, BC-010, BC-007 | **Medium** | F-128, F-129, F-070 |
| F-128 | Incoming Call System (Voice-First) | AI-powered voice-first response using STT, AI reasoning, and TTS to resolve queries without human intervention | AI / Backend | BC-005, BC-007, BC-010 | **Medium** | F-127, F-054, F-065 |
| F-129 | Proactive Outbound Voice (Abandoned Carts) | Automated outbound voice calls targeting abandoned carts with personalized AI-generated reminders | AI / Backend | BC-005, BC-007, BC-002 | **Low** | F-127, F-070, F-072 |
| F-130 | Social Media Integration | Unified inbox for social channels (Twitter/X, Facebook, Instagram) with sentiment-aware routing | Frontend / Backend | BC-005, BC-001, BC-003 | **Medium** | F-070, F-062, F-063 |

> **Note:** Each channel follows the **intake → classify → route → respond → track** pipeline with channel-specific handling for quirks (email threading, SMS limits, voice latency, social public/private).

---

## Category 13: Integrations & Extensibility

| ID | Name | Description | Area | Building Codes | Priority | Dependencies |
|----|------|-------------|------|----------------|----------|-------------|
| F-131 | Pre-built Connectors | Ready-to-use connectors: Shopify, GitHub, TMS/WMS, Stripe, Zendesk, Intercom — each with guided auth and auto-sync | Backend | BC-001, BC-003, BC-004 | **Critical** | F-137, F-070 |
| F-132 | Custom REST API Connector | User-configurable REST integration with custom endpoints, auth methods (API key, OAuth2, Basic), and data mapping | Backend / Frontend | BC-003, BC-011, BC-001 | **High** | F-137, F-134 |
| F-133 | GraphQL Integration | Native GraphQL client for platforms with GraphQL APIs, with query builder UI and subscription support | Backend | BC-003, BC-005, BC-001 | **Medium** | F-132, F-137 |
| F-134 | Webhook Integration (Incoming) | HTTP POST receiver validating signatures, transforming payloads, and routing events to PARWA workflows | Backend | BC-003, BC-011, BC-012 | **High** | F-131, F-132, F-060 |
| F-135 | MCP Integration | Model Context Protocol support enabling agents to use external tools via standardized MCP server connections | AI / Backend | BC-007, BC-003, BC-001 | **High** | F-054, F-060, F-064 |
| F-136 | Database Connection Integration | Secure DB connector (PostgreSQL, MySQL, MongoDB, Redis) for real-time order lookups and inventory checks | Backend | BC-011, BC-001, BC-003 | **High** | F-064, F-131 |
| F-137 | Integration Health Monitor | Real-time dashboard monitoring all integrations: status, last sync, error rates, latency, auto-alerting | Frontend / Backend | BC-012, BC-005, BC-003 | **High** | F-131, F-132, F-093, F-088 |
| F-138 | Outgoing Webhooks | Send webhook events from PARWA to external systems on specified actions (ticket resolved, refund issued) with retry logic | Backend | BC-003, BC-012, BC-004 | **High** | F-134, F-060, F-139 |
| F-139 | Circuit Breaker | Circuit breaker pattern stopping failing integrations with recovery cooldown and graceful degradation | Backend / Infra | BC-012, BC-003, BC-004 | **Critical** | F-137, F-138, F-093, F-094 |

> **Note:** Every outbound call passes through the circuit breaker (F-139). Combined with Health Monitor (F-137) and Trust Preservation Protocol (F-094), external failures never cascade into customer-facing breakdowns.

---

## Complete Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Major Features** | 139 |
| **Categories** | 13 |
| **Critical Priority** | 38 |
| **High Priority** | 68 |
| **Medium Priority** | 27 |
| **Low Priority** | 6 |
| **AI-related Features** | 62 |
| **Backend Features** | 95 |
| **Frontend Features** | 72 |
| **Infrastructure Features** | 12 |

### Building Code Coverage Summary

| Building Code | Description | Feature Count |
|--------------|-------------|---------------|
| BC-012 | Error Handling & Resilience | 98 |
| BC-001 | Multi-Tenant Isolation | 72 |
| BC-007 | AI Model Interaction | 65 |
| BC-005 | Real-Time Communication | 48 |
| BC-003 | Webhook Handling | 38 |
| BC-004 | Background Jobs | 36 |
| BC-009 | Approval Workflow | 27 |
| BC-011 | Authentication & Security | 30 |
| BC-002 | Financial Actions | 25 |
| BC-006 | Email Communication | 20 |
| BC-008 | State Management | 18 |
| BC-010 | Data Lifecycle & Compliance | 19 |

### Top 10 Most-Depended Features

| Feature | Name | Downstream Dependencies |
|---------|------|------------------------|
| F-013 | Login System | 12 features |
| F-001 | Landing Page | 8 features |
| F-004 | Pricing Page | 7 features |
| F-046 | Ticket List | 7 features |
| F-036 | Dashboard Home | 10 features |
| F-034 | AI Activation | 5 features |
| F-054 | Smart Router | 14 features |
| F-059 | Confidence Scoring | 9 features |
| F-097 | Agent Dashboard | 5 features |
| F-074 | Approval Queue | 7 features |

---

*PARWA Feature Catalog v1.0 — Generated March 2026*





Building Codes v1.0

Production Patterns for Loophole Prevention

Part 1 of 2 --- BC-001 to BC-006

March 2026

CONFIDENTIAL --- Internal Engineering Reference

  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

**Table of Contents**

BC-001: Multi-Tenant Isolation 3

> Purpose 3
>
> When to Apply 3
>
> Mandatory Rules 3
>
> Implementation Pattern 4
>
> Loophole Checklist 4

BC-002: Financial Actions 5

> Purpose 5
>
> When to Apply 5
>
> Mandatory Rules 6
>
> Implementation Pattern 7
>
> Loophole Checklist 7

BC-003: Webhook Handling 8

> Purpose 8
>
> When to Apply 8
>
> Mandatory Rules 9
>
> Implementation Pattern 9
>
> Loophole Checklist 10

BC-004: Background Jobs 10

> Purpose 10
>
> When to Apply 11
>
> Mandatory Rules 11
>
> Implementation Pattern 12
>
> Loophole Checklist 12

BC-005: Real-Time Communication 13

> Purpose 13
>
> When to Apply 13
>
> Mandatory Rules 14
>
> Implementation Pattern 14
>
> Loophole Checklist 15

BC-006: Email Communication 15

> Purpose 15
>
> When to Apply 16
>
> Mandatory Rules 16
>
> Implementation Pattern 17
>
> Loophole Checklist 17

Note: Right-click the Table of Contents and select "Update Field" to
refresh page numbers after editing.

**BC-001: Multi-Tenant Isolation**

**Purpose**

This building code prevents the most critical security vulnerability in
any multi-tenant system: one client accessing or seeing another client's
data. In PARWA's multi-tenant architecture, every table carries a
company_id column, and this code ensures that every single data access
--- whether from an API route, a Celery background worker, a Socket.io
event handler, or an MCP server --- is strictly scoped to the requesting
tenant's company_id. Failure to enforce tenant isolation results in
cross-tenant data leakage, which constitutes a severe security breach
and potential GDPR violation. This is Loophole #8 from the PARWA
loophole registry.

**When to Apply**

Every feature that reads, writes, or processes any data stored in
PostgreSQL or Redis MUST comply with this building code. This includes
all REST API endpoints, all Celery task definitions, all Socket.io event
handlers, all webhook processors, all MCP server endpoints, and any
internal utility functions that query the database. There are zero
exceptions --- even administrative or debugging endpoints must respect
tenant isolation. During code review, any database query lacking a
company_id filter must be rejected.

**Mandatory Rules**

1.  Every database query MUST include WHERE company_id = :tenant_id. No
    query may return unscoped data, regardless of the table or use case.

2.  Celery workers MUST receive company_id as an explicit task
    parameter. Workers do not have auth context and cannot derive tenant
    identity from JWT tokens.

3.  Socket.io rooms MUST be scoped by company_id using the naming
    convention room: tenant\_{company_id}. A client MUST NEVER join a
    global or cross-tenant room.

4.  Every API response MUST be filtered by company_id. Even if a query
    internally uses tenant scoping, the API layer must verify that no
    cross-tenant data is present in the response payload.

5.  Application-level Row-Level Security (RLS) MUST be enforced via
    middleware. The middleware extracts tenant_id from the JWT token and
    injects it into every database session as a default filter
    condition.

6.  Integration tests MUST create at least 3 test tenants and verify
    that no data created by one tenant is visible to another tenant
    under any circumstances.

7.  Redis keys MUST be namespaced with company_id prefix (e.g.,
    parwa:{company_id}:session:{session_id}) to prevent cross-tenant
    cache or state access.

8.  Database indexes on company_id MUST exist on every table that stores
    tenant-specific data. Query performance must not degrade due to the
    mandatory tenant filter.

**Implementation Pattern**

> \# Middleware: Tenant Isolation (FastAPI)
>
> \@app.middleware(\"http\")
>
> async def tenant_isolation(request, call_next):
>
> token = request.headers.get(\"Authorization\")
>
> payload = decode_jwt(token)
>
> company_id = payload.get(\"company_id\")
>
> if not company_id:
>
> raise HTTPException(401, \"Tenant not identified\")
>
> request.state.company_id = company_id
>
> \# Inject into DB session
>
> db.execute(\"SET app.current_tenant = :tid\", {\"tid\": company_id})
>
> response = await call_next(request)
>
> return response
>
> \# Celery Task: company_id as first parameter
>
> \@celery.task(bind=True, max_retries=3)
>
> def process_ticket(self, company_id, ticket_id, action):
>
> tickets = db.query(Ticket).filter(
>
> Ticket.company_id == company_id,
>
> Ticket.id == ticket_id
>
> ).first()
>
> if not tickets:
>
> raise ValueError(\"Ticket not found or cross-tenant\")
>
> \# Socket.io: tenant-scoped rooms
>
> def join_tenant_room(sid, company_id):
>
> room = f\"tenant\_{company_id}\"
>
> sio.enter_room(sid, room)

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Create Tenant A and Tenant B. Create a ticket in Tenant A's
    workspace. Attempt to fetch that ticket using Tenant B's API
    credentials. The result MUST be 404 or an empty response.

2.  Submit a Celery task with company_id for Tenant A but ticket_id
    belonging to Tenant B. The task MUST fail with a cross-tenant access
    error.

3.  Connect a Socket.io client authenticated as Tenant A. Emit a message
    to Tenant B's room. The message MUST NOT be delivered to Tenant B's
    clients.

4.  Directly query the PostgreSQL database without a company_id filter
    in a test script. Verify that the RLS middleware blocks or filters
    the result.

5.  Create a Redis key under parwa:tenant_A:cache:data. Attempt to read
    it using tenant_B's Redis namespace. The read MUST return null.

6.  Run the integration test suite with 3+ tenants and verify zero data
    leakage assertions pass.

**BC-002: Financial Actions**

**Purpose**

This building code addresses every money-related loophole in the PARWA
platform (#10, #14, #15, #16, #17, #18). Financial operations ---
including subscription billing, overage charges, refunds, agent
provisioning, and payment processing --- are the highest-risk actions in
the system. A single bug in financial logic can result in
double-charging customers, failing to charge for usage, or processing
fraudulent refunds. This code mandates idempotency, atomicity, audit
trails, and approval workflows for all financial operations, with
specific rules for Paddle integration as PARWA's payment provider (not
Stripe).

**When to Apply**

All features involving money, billing, subscriptions, refunds, credits,
overage charges, agent provisioning (which is tied to billing), and
payment collection. This includes the subscription management module,
the billing dashboard, the overage calculation engine, the refund
processing workflow, the voice demo payment flow, and the temporary
agent lifecycle. Any new feature that touches the Paddle API or modifies
financial records in the database must comply with this building code in
its entirety.

**Mandatory Rules**

1.  All financial operations MUST have an approval record created before
    execution. The record must capture the action type, amount, actor,
    timestamp, and current state (pending, approved, executed, failed,
    rolled_back).

2.  Paddle API calls MUST implement idempotency. Before processing any
    webhook or API response, the system MUST check the webhook_events
    table for the paddle_event_id. If already processed, return 200
    without re-executing.

3.  All financial amounts MUST be stored as DECIMAL(10,2) in PostgreSQL.
    Floating-point arithmetic (Python float, JavaScript number) MUST
    NEVER be used for monetary calculations. Use the decimal module in
    Python.

4.  Rate limiting on financial endpoints MUST be applied per user
    account (not per IP address). A single user must not be able to
    trigger rapid successive financial operations.

5.  All DB updates within a financial transaction MUST be wrapped in a
    single atomic database transaction. If any step fails, the entire
    transaction rolls back.

6.  If a Paddle API call fails after a successful DB update, the DB
    changes MUST be rolled back immediately. Implement a compensation
    transaction pattern for distributed operations.

7.  Daily overage charges MUST include an idempotency check on the
    combination of date + company_id before creating a new charge.
    Prevent duplicate daily charges.

8.  Every financial action MUST be logged in the audit_trail table with:
    amount, currency, actor (user_id), action_type, timestamp, and
    resulting state.

9.  Paddle webhook double-fire MUST be prevented via the webhook_events
    table with a UNIQUE constraint on paddle_event_id.

10. Subscription changes (upgrade, downgrade, cancellation) MUST
    delegate proration to Paddle's API. Agent de-provisioning on
    downgrade MUST be scheduled via Celery with appropriate delays.

11. Temporary agents MUST have an expiry_at timestamp. A Celery beat job
    MUST check daily for expired temporary agents and auto-deprovision
    them.

12. Voice demo feature MUST collect the customer's phone number ONLY
    after payment confirmation is received. If payment fails, any
    collected phone data MUST be cleared immediately.

**Implementation Pattern**

> \# Financial Transaction Pattern
>
> async def process_overage(company_id, amount, date):
>
> \# Idempotency check
>
> exists = db.query(OverageCharge).filter(
>
> OverageCharge.company_id == company_id,
>
> OverageCharge.charge_date == date
>
> ).first()
>
> if exists:
>
> return {\"status\": \"already_charged\"}
>
> async with db.transaction():
>
> \# Create approval record
>
> approval = ApprovalRecord.create(
>
> company_id=company_id,
>
> action=\"overage_charge\",
>
> amount=Decimal(str(amount)),
>
> status=\"approved_auto\"
>
> )
>
> \# Call Paddle
>
> paddle_result = await paddle_client.charge(
>
> company_id=company_id,
>
> amount=Decimal(str(amount)),
>
> idempotency_key=f\"{company_id}\_{date}\"
>
> )
>
> if not paddle_result.success:
>
> raise PaymentError(\"Paddle charge failed\")
>
> \# Log audit trail
>
> AuditTrail.log(
>
> company_id=company_id,
>
> action=\"overage_charge\",
>
> amount=Decimal(str(amount)),
>
> paddle_tx_id=paddle_result.tx_id
>
> )

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Trigger the same overage charge webhook twice with the same
    paddle_event_id. The system MUST process it only once and return 200
    on the second attempt.

2.  Process a subscription downgrade. Verify that Paddle handles
    proration and that a Celery task is scheduled to deprovision excess
    agents after the downgrade period.

3.  Create a temporary agent with expiry_at set to yesterday. Run the
    Celery beat expiry check. The agent MUST be deprovisioned and its
    status updated.

4.  Simulate a Paddle API timeout during a charge. Verify the database
    transaction rolls back and no partial state is left.

5.  Submit a refund request for an amount larger than the original
    charge. The system MUST reject this with a validation error.

6.  Attempt a voice demo flow where payment fails at the confirmation
    step. Verify no phone number is stored in the database.

**BC-003: Webhook Handling**

**Purpose**

This building code prevents fake webhooks and double-processing of
webhook events (Loopholes #9 and #10). Webhooks from external services
such as Paddle, Shopify, Twilio, and Brevo are the primary input
channels for asynchronous events. Without proper verification, an
attacker could forge webhook payloads to trigger unauthorized actions
(fake payments, fake orders, fake SMS confirmations). Without
idempotency, network retries or provider re-deliveries could cause the
same event to be processed multiple times, resulting in duplicate
charges, duplicate ticket creation, or duplicate notifications. This
code establishes a rigorous webhook verification, processing, and
logging framework.

**When to Apply**

Every webhook endpoint in the PARWA system must comply with this
building code. This includes: Paddle billing webhooks (subscription
events, payment events, refund events), Shopify integration webhooks
(order created, order updated), Twilio SMS/Voice status webhooks, and
Brevo email event webhooks (delivered, bounced, complained). Any future
integration that receives webhooks from an external provider must follow
this pattern before being deployed to production.

**Mandatory Rules**

1.  Every webhook endpoint MUST verify the HMAC/signature provided by
    the sender BEFORE processing the payload. Unverified webhooks MUST
    be rejected with HTTP 403.

2.  Paddle webhook verification: compute HMAC-SHA256 using the
    PADDLE_WEBHOOK_SECRET and compare with the signature header. Use
    constant-time comparison to prevent timing attacks.

3.  Shopify webhook verification: compute HMAC using the
    SHOPIFY_API_SECRET and the raw request body, compare with the
    X-Shopify-Hmac-Sha256 header.

4.  Twilio webhook verification: use the Twilio SDK's validate_request
    method to verify the X-Twilio-Signature header against the
    configured AUTH_TOKEN.

5.  Brevo webhook verification: implement IP allowlist checking. Only
    accept requests from Brevo's documented IP ranges. Log and reject
    requests from non-allowlisted IPs.

6.  All webhooks MUST implement idempotency. Store the event ID
    (provider-specific) in the webhook_events table with a UNIQUE
    constraint. Before processing, check for existence. If exists,
    return 200 immediately.

7.  Webhook processing MUST be asynchronous. The endpoint should
    validate the signature, store the raw payload in webhook_events with
    status=pending, queue a Celery task for processing, and return 200
    OK within 3 seconds.

8.  Failed webhook processing MUST retry up to 3 times with exponential
    backoff (60s, 300s, 900s). After max retries, mark the event as
    failed and alert the operations team.

9.  Every webhook MUST be logged in the webhook_events table with:
    provider, event_id, event_type, payload (JSON), status
    (pending/processing/completed/failed), created_at, processed_at,
    error_message.

10. The webhook endpoint MUST respond with HTTP 200 within 3 seconds of
    receiving the request, even if actual processing is deferred to a
    background task.

11. Rate limit webhook endpoints to prevent abuse. A single IP or sender
    must not be able to flood the webhook endpoint with thousands of
    requests.

**Implementation Pattern**

> \# Webhook Handler Pattern (FastAPI)
>
> \@app.post(\"/webhooks/paddle\")
>
> async def paddle_webhook(request: Request):
>
> raw_body = await request.body()
>
> signature = request.headers.get(\"paddle-signature\")
>
> \# 1. Verify HMAC-SHA256
>
> if not verify_paddle_hmac(raw_body, signature):
>
> logger.warning(\"Invalid Paddle webhook signature\")
>
> raise HTTPException(403, \"Invalid signature\")
>
> payload = json.loads(raw_body)
>
> event_id = payload.get(\"event_id\")
>
> \# 2. Idempotency check
>
> existing = db.query(WebhookEvent).filter(
>
> WebhookEvent.event_id == event_id
>
> ).first()
>
> if existing:
>
> return {\"status\": \"already_processed\"}
>
> \# 3. Store and queue
>
> event = WebhookEvent.create(
>
> provider=\"paddle\",
>
> event_id=event_id,
>
> event_type=payload.get(\"event_type\"),
>
> payload=payload,
>
> status=\"pending\"
>
> )
>
> process_paddle_webhook.delay(event.id)
>
> return {\"status\": \"accepted\"}

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Send a Paddle webhook with an invalid HMAC signature. The endpoint
    MUST return 403 and not process the payload.

2.  Send the same valid Paddle webhook twice. The second delivery MUST
    return 200 with already_processed status, and the side effect MUST
    occur only once.

3.  Send a webhook with a malformed payload that causes the processing
    task to fail. Verify that the retry mechanism triggers up to 3 times
    with exponential backoff.

4.  Send a Twilio webhook with an invalid X-Twilio-Signature. The
    endpoint MUST reject it.

5.  Send a Brevo webhook from a non-allowlisted IP address. The endpoint
    MUST reject it and log the attempt.

6.  Flood a webhook endpoint with 1000 requests per second. The rate
    limiter MUST throttle requests after the configured threshold.

**BC-004: Background Jobs (Celery)**

**Purpose**

This building code prevents silent failures, lost jobs, and cross-tenant
data leakage in background job processing (Loopholes #3, #4, #7). Celery
background workers handle critical tasks including email sending, AI
processing, report generation, agent provisioning, and data cleanup.
Because these tasks run outside the request-response cycle, failures are
inherently invisible unless explicitly monitored. A failed Celery task
could silently drop a customer email, skip a billing charge, or leave an
agent in a half-provisioned state. This code mandates comprehensive
error handling, retry logic, dead letter queuing, and tenant context
propagation for every Celery task in the system.

**When to Apply**

Every Celery task definition in the PARWA codebase must comply with this
building code. This includes all tasks decorated with \@celery.task or
\@app.task, regardless of whether they are scheduled (Celery beat),
triggered by API endpoints, or dispatched by webhook handlers.
Specifically: email sending tasks, AI model invocation tasks, report
generation tasks, agent provisioning/deprovisioning tasks, data export
tasks, cleanup/maintenance tasks, and any task that interacts with the
database or external APIs.

**Mandatory Rules**

1.  Every Celery task MUST accept company_id as its first parameter
    (after self for bound tasks). This ensures tenant context is always
    available even when the task runs without HTTP request context.

2.  Every Celery task MUST define max_retries=3. The retry backoff MUST
    be exponential (2\^n seconds where n is the retry attempt number).
    Use self.retry_with(countdown=2\*\*self.request.retries) for bound
    tasks.

3.  Every Celery task MUST have a timeout configured. The default
    timeout is 300 seconds (5 minutes). Tasks that interact with
    external APIs may configure a longer timeout via the soft_time_limit
    and time_limit parameters.

4.  Tasks that have exhausted max_retries MUST be routed to a Dead
    Letter Queue (DLQ). The DLQ is a separate Celery queue (named 'dlq')
    that stores failed tasks for inspection and manual retry.

5.  When a task enters the DLQ, an alert MUST be sent to the operations
    team via email (to admin) or Slack webhook. The alert must include
    the task name, arguments, failure reason, and timestamp.

6.  Redis persistence MUST be configured with AOF (Append-Only File)
    enabled and RDB snapshots every 15 minutes. This ensures task
    metadata survives a Redis restart without data loss.

7.  Celery beat schedules MUST be defined in the beat_schedule
    configuration dictionary, not hardcoded in task bodies. All
    scheduled tasks must be centrally visible and configurable.

8.  GSD State MUST use Redis as the primary store and PostgreSQL
    (sessions table) as a fallback. On every state update, the state
    MUST be saved to both Redis and PostgreSQL.

9.  On Redis restart, active session states MUST be recovered from the
    PostgreSQL fallback. A recovery task MUST run on Celery worker
    startup to hydrate Redis from Postgres.

10. Every Celery task MUST log start_time, end_time, and duration in the
    task_logs table. This data is used for performance monitoring and
    SLA tracking.

**Implementation Pattern**

> \# Celery Task Pattern
>
> \@celery.task(
>
> bind=True,
>
> max_retries=3,
>
> soft_time_limit=300,
>
> time_limit=330,
>
> queue=\"default\"
>
> )
>
> def send_email_task(self, company_id, template_id, recipient):
>
> start = time.time()
>
> try:
>
> \# Tenant-scoped query
>
> template = db.query(EmailTemplate).filter(
>
> EmailTemplate.company_id == company_id,
>
> EmailTemplate.id == template_id
>
> ).first()
>
> if not template:
>
> raise ValueError(\"Template not found\")
>
> brevo_client.send(
>
> template_id=template.brevo_id,
>
> to=recipient,
>
> params=template.default_params
>
> )
>
> \# Log success
>
> TaskLog.create(
>
> task_name=\"send_email_task\",
>
> company_id=company_id,
>
> start_time=start,
>
> end_time=time.time(),
>
> duration=time.time() - start,
>
> status=\"success\"
>
> )
>
> except Exception as exc:
>
> \# Retry with exponential backoff
>
> raise self.retry_with(
>
> exc=exc,
>
> countdown=2 \*\* self.request.retries
>
> )

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Submit a Celery task that raises an exception. Verify it retries 3
    times with exponential backoff (2s, 4s, 8s) and then routes to the
    DLQ.

2.  Verify that a DLQ alert is sent when a task fails all retries. Check
    that the alert contains the task name, arguments, and error details.

3.  Submit a task with company_id for Tenant A but with data belonging
    to Tenant B. The task MUST fail with a cross-tenant error.

4.  Restart Redis while Celery workers are processing tasks. Verify that
    AOF persistence allows recovery and no tasks are lost.

5.  Simulate a long-running task that exceeds the 300s timeout. Verify
    the task is killed and marked as failed.

6.  Check the task_logs table after running 10 tasks. Verify each entry
    has accurate start_time, end_time, and duration values.

**BC-005: Real-Time Communication (Socket.io)**

**Purpose**

This building code prevents lost events and connection-related data loss
(Loophole #2). PARWA uses Socket.io to provide real-time updates to the
dashboard, including new ticket notifications, AI response streaming,
agent status changes, and approval queue updates. In a production
environment, WebSocket connections are inherently unreliable --- network
switches, mobile network transitions, proxy timeouts, and server
restarts can all cause disconnections. Without a robust reconnection
strategy and event buffering, customers could miss critical
notifications or see stale dashboard state. This code ensures that
real-time communication is resilient to disconnections and provides
graceful degradation when Socket.io is unavailable.

**When to Apply**

All features that use Socket.io for real-time communication must comply
with this building code. This includes: the live dashboard (ticket
stream, agent status), AI response streaming (typing indicators, partial
responses), approval queue real-time updates, notification push events,
and any feature that emits events to clients via WebSocket. Any new
feature requiring real-time bidirectional communication must be
evaluated against this building code before implementation.

**Mandatory Rules**

1.  Client-side reconnection MUST implement exponential backoff: 1s, 2s,
    4s, 8s, 16s, capped at 30s maximum. The client must not attempt to
    reconnect more frequently than this schedule.

2.  On reconnect, the client MUST call GET
    /api/events/since?last_seen={timestamp} to fetch all events that
    occurred during the disconnection period. The server returns events
    from the event buffer table.

3.  Server-side: every Socket.io emit MUST also store the event in an
    event_buffer table with columns: tenant_id, event_type, payload
    (JSONB), created_at. This ensures events survive client
    disconnections.

4.  Event buffer retention MUST be 24 hours. A Celery beat task MUST run
    daily to delete events older than 24 hours from the event_buffer
    table.

5.  Socket.io rooms MUST be scoped by tenant_id using the naming
    convention tenant\_{company_id}. A client MUST NEVER join a global
    room or a room belonging to another tenant.

6.  Graceful degradation: if Socket.io is unavailable, the dashboard
    MUST still function on page refresh. All critical data must be
    available via REST API endpoints. Socket.io is an enhancement, not a
    requirement.

7.  Nginx MUST be configured with sticky sessions (ip_hash) for
    Socket.io connections. This prevents connection drops during rolling
    deployments.

8.  Emergency pause: when AI is paused (e.g., Guardrails block), events
    MUST still be emitted to connected clients with a pause context
    flag, allowing the UI to display appropriate messaging.

**Implementation Pattern**

> \# Client-Side Reconnection (Next.js)
>
> const socket = io({
>
> reconnection: true,
>
> reconnectionAttempts: Infinity,
>
> reconnectionDelay: 1000,
>
> reconnectionDelayMax: 30000,
>
> });
>
> let lastSeen = Date.now();
>
> socket.on(\"disconnect\", async () =\> {
>
> console.log(\"Disconnected, will reconnect\...\");
>
> });
>
> socket.on(\"connect\", async () =\> {
>
> // Fetch missed events
>
> const { data } = await axios.get(
>
> \`/api/events/since?last_seen=\${lastSeen}\`
>
> );
>
> data.events.forEach(e =\> handleEvent(e));
>
> });
>
> socket.on(\"event\", (e) =\> {
>
> lastSeen = e.timestamp;
>
> handleEvent(e);
>
> });

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Connect a client, emit 5 events, disconnect the client, emit 3 more
    events, then reconnect. The client MUST receive all 8 events total
    (5 live + 3 from the buffer).

2.  Simulate a server restart while 10 clients are connected. Verify
    that all clients reconnect within the exponential backoff schedule
    and recover missed events.

3.  Connect a client authenticated as Tenant A. Verify it only receives
    events for Tenant A's room. Emit an event to Tenant B's room. Tenant
    A's client MUST NOT receive it.

4.  Disable Socket.io entirely (kill the Socket.io process). Verify the
    dashboard still loads and displays current data via REST API on page
    refresh.

5.  Trigger an AI pause event. Verify the Socket.io emit includes the
    pause context flag and the UI displays the appropriate paused state
    messaging.

6.  Check the event_buffer table after 25 hours. Verify that events
    older than 24 hours have been cleaned up by the Celery beat task.

**BC-006: Email Communication (Brevo)**

**Purpose**

This building code prevents email loops, spam, and missed inbound emails
(Loophole #28). PARWA uses Brevo for both outbound transactional emails
(ticket responses, notifications, reports) and inbound email parsing
(customer replies converted to tickets). Email systems are particularly
vulnerable to loops: an auto-response from PARWA could trigger another
auto-response from the customer's email system, creating an infinite
loop that wastes resources and spams both parties. Additionally,
outbound emails must be rate-limited to prevent PARWA from being flagged
as a spam source. This code establishes guardrails for both inbound and
outbound email communication.

**When to Apply**

All features that send or receive emails must comply with this building
code. This includes: outbound transactional emails (ticket responses,
password reset, welcome emails, notification emails), Brevo template
management, inbound email parsing (Brevo Parse webhook), auto-response
systems, email-based ticket creation, marketing/notification emails with
unsubscribe links, and bounce/complaint handling. Any new email template
or email-triggering feature must be reviewed against these rules before
deployment.

**Mandatory Rules**

1.  Auto-Reply / Out-of-Office (OOO) detection: before sending any
    automated email response, the system MUST check the inbound email
    headers for X-Auto-Response-Suppress and Auto-Submitted headers. If
    present, do NOT send an auto-reply.

2.  Maximum replies per thread: the system MUST NOT send more than 5
    automated responses per thread per 24-hour period per customer email
    address. This prevents infinite loops even if OOO detection fails.

3.  Rate limiting: the system MUST NOT send more than 5 emails per
    customer per hour. This applies across all email types
    (transactional, notifications, alerts).

4.  Every outbound email MUST use a Brevo template. PARWA defines
    exactly 10 Brevo templates. Hardcoded email bodies in application
    code are prohibited.

5.  Every outbound email MUST be logged in the email_logs table with:
    template_used, recipient, status (sent/delivered/bounced/failed),
    timestamp, and related_entity (ticket_id, user_id, etc.).

6.  Inbound email processing (Brevo Parse webhook): the webhook handler
    MUST check for email loops before creating a new ticket or adding a
    message to an existing thread. Check headers and the 5-per-24h
    limit.

7.  Marketing and notification emails MUST include an unsubscribe link.
    Transactional emails (direct responses to customer inquiries) are
    exempt from this requirement.

8.  Bounce and complaint handling: Brevo webhooks for bounce and
    complaint events MUST update the customer's email status to
    'invalid' and notify the account manager.

9.  Email sending failures MUST be retried up to 3 times with
    exponential backoff. After 3 failures, log the failure and alert the
    operations team.

**Implementation Pattern**

> \# Inbound Email Handler Pattern
>
> \@app.post(\"/webhooks/brevo/inbound\")
>
> async def inbound_email(request: Request):
>
> \# 1. IP allowlist check
>
> if not is_brevo_ip(request.client.host):
>
> raise HTTPException(403, \"IP not allowlisted\")
>
> payload = await request.json()
>
> sender = payload\[\"from\"\]
>
> \# 2. OOO detection
>
> headers = payload.get(\"headers\", {})
>
> if headers.get(\"X-Auto-Response-Suppress\"):
>
> return {\"status\": \"auto_reply_ignored\"}
>
> if headers.get(\"Auto-Submitted\"):
>
> return {\"status\": \"auto_reply_ignored\"}
>
> \# 3. Rate limit check (5 per thread per 24h)
>
> thread_id = payload.get(\"thread_id\")
>
> count_24h = db.query(EmailLog).filter(
>
> EmailLog.thread_id == thread_id,
>
> EmailLog.created_at \> now() - timedelta(hours=24)
>
> ).count()
>
> if count_24h \>= 5:
>
> return {\"status\": \"rate_limited\"}
>
> \# 4. Process email
>
> ticket = create_or_update_ticket(payload)
>
> return {\"status\": \"processed\", \"ticket_id\": ticket.id}

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Send an inbound email with X-Auto-Response-Suppress header. Verify
    the system ignores it and does not create a ticket or send a reply.

2.  Send 6 automated responses to the same thread within 24 hours.
    Verify the 6th response is suppressed by the rate limiter.

3.  Send 6 emails to the same customer within 1 hour. Verify the 6th
    email is blocked by the per-customer rate limit.

4.  Trigger a Brevo bounce webhook for a customer email. Verify the
    email is marked as invalid and the manager is notified.

5.  Send an inbound email from an address that previously complained
    (Brevo complaint webhook). Verify the email is not processed.

6.  Verify every outbound email in the email_logs table has a valid
    template_used value matching one of the 10 defined Brevo templates.
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

**PARWA**

  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

Building Codes v1.0

Production Patterns for Loophole Prevention

**Part 2 of 2 --- BC-007 to BC-012**

March 2026

CONFIDENTIAL --- Internal Engineering Reference

  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

**Table of Contents**

BC-007: AI Model Interaction (Smart Router) 1

> Purpose 1
>
> When to Apply 1
>
> Mandatory Rules 1
>
> Implementation Pattern 3
>
> Loophole Checklist 4

BC-008: State Management (GSD Engine) 5

> Purpose 5
>
> When to Apply 5
>
> Mandatory Rules 6
>
> Implementation Pattern 7
>
> Loophole Checklist 8

BC-009: Approval Workflow 9

> Purpose 9
>
> When to Apply 9
>
> Mandatory Rules 10
>
> Implementation Pattern 11
>
> Loophole Checklist 12

BC-010: Data Lifecycle & Compliance 13

> Purpose 13
>
> When to Apply 13
>
> Mandatory Rules 14
>
> Implementation Pattern 15
>
> Loophole Checklist 16

BC-011: Authentication & Security 17

> Purpose 17
>
> When to Apply 17
>
> Mandatory Rules 18
>
> Implementation Pattern 19
>
> Loophole Checklist 21

BC-012: Error Handling & Resilience 22

> Purpose 22
>
> When to Apply 22
>
> Mandatory Rules 23
>
> Implementation Pattern 24
>
> Loophole Checklist 25

Note: Right-click the Table of Contents and select "Update Field" to
refresh page numbers after editing.

**BC-007: AI Model Interaction (Smart Router)**

**Purpose**

This building code prevents rate limit exhaustion, model availability
failures, content safety violations, and invalid response parsing in all
AI model interactions. PARWA relies on multiple LLM providers through
OpenRouter to deliver AI-driven customer support. The Smart Router is a
centralized orchestration layer that manages model selection, failover,
PII protection, and content safety. Without this building code, a single
model outage could disable all AI functionality, rate limits could
cascade across requests, PII could leak into LLM context windows, and
unsafe content could reach end users.

**When to Apply**

Every feature that calls an LLM through OpenRouter or any AI provider
must comply with this building code. This includes the GSD
conversational AI engine, ticket classification, sentiment analysis,
knowledge base search augmentation, agent training feedback loops, and
any future AI-powered features. Any code path that sends user-generated
content to an external AI model is in scope, regardless of whether the
output is displayed to users or used internally.

**Mandatory Rules**

1.  The Smart Router MUST maintain a priority-ordered model list for
    each tier: Light (classification, tagging), Medium (standard
    responses, summarization), and Heavy (complex reasoning, knowledge
    synthesis).

2.  Model configuration (provider, model ID, API key, priority, tier)
    MUST be stored in the api_providers database table. Admins MUST be
    able to add, remove, or reorder models without a code deployment.

3.  When a 429 (rate limit) response is received, the Smart Router MUST
    immediately try the next model in the same tier. If all models in
    the tier are rate-limited, it MUST fall back to the next tier (Light
    → Medium → Heavy).

4.  If ALL models across all tiers return 429, the request MUST be
    queued for retry and the user MUST receive an immediate response
    stating their request is being processed.

5.  PII redaction MUST occur BEFORE any content is sent to an LLM AND
    before any LLM output is stored in the database. The PII redaction
    engine MUST scan for email addresses, phone numbers, names, credit
    card numbers, and addresses using regex patterns and optionally a
    named entity recognition model.

6.  Guardrails AI MUST evaluate every LLM response before delivery to
    the user. If Guardrails blocks a response, the system MUST fall back
    to a safe default template response. The blocked response MUST be
    logged with the original prompt, model output, and blocking reason
    for manager review.

7.  A manager review queue MUST exist where blocked responses can be
    inspected and optionally released. Released responses MUST pass
    through a second Guardrails check before delivery.

8.  If an LLM returns invalid JSON (malformed, missing required fields),
    the system MUST retry with a simplified prompt that explicitly
    requests valid JSON. If the retry also fails, the system MUST fall
    back to a pre-defined response template.

9.  Confidence thresholds for auto-action MUST be stored per company in
    the database, not hardcoded in application logic. Each company can
    configure their own confidence thresholds for different action
    types.

10. The AI training feedback threshold is LOCKED at 50 mistakes. This
    value cannot be changed by any admin or configuration. When a model
    accumulates 50 mistake reports from a company, it MUST be
    automatically flagged for retraining and removed from the active
    model rotation.

**Implementation Pattern**

> \# Smart Router Pattern (Python)
>
> class SmartRouter:
>
> def \_\_init\_\_(self, company_id, tier):
>
> self.company_id = company_id
>
> self.tier = tier
>
> self.models = db.query(ApiProvider).filter(
>
> ApiProvider.tier == tier
>
> ).order_by(ApiProvider.priority).all()
>
> async def route(self, prompt, context):
>
> \# PII Redaction BEFORE LLM call
>
> redacted_prompt = pii_engine.redact(
>
> prompt, self.company_id
>
> )
>
> redacted_context = pii_engine.redact(
>
> context, self.company_id
>
> )
>
> for model in self.models:
>
> try:
>
> response = await openrouter.call(
>
> model=model.model_id,
>
> prompt=redacted_prompt,
>
> context=redacted_context
>
> )
>
> \# Validate JSON
>
> parsed = self.\_validate_json(response)
>
> \# Guardrails check
>
> safe = await guardrails.evaluate(
>
> parsed, self.company_id
>
> )
>
> if safe.blocked:
>
> log_blocked(safe.reason, parsed)
>
> return self.\_safe_fallback()
>
> \# PII redact output before DB store
>
> clean_output = pii_engine.redact(
>
> parsed, self.company_id
>
> )
>
> return clean_output
>
> except RateLimitError:
>
> continue \# Try next model
>
> except InvalidJSONError:
>
> return self.\_retry_simplified(
>
> redacted_prompt
>
> redacted_context
>
> )
>
> \# All models rate-limited: queue it
>
> queue_request(self.company_id, prompt)
>
> return {\"status\": \"processing\"}

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Send 100 rapid requests to trigger 429 on the first model. Verify
    the Smart Router falls back to the next model in the same tier
    without user-visible delay.

2.  Configure only one model in the Light tier and trigger a 429. Verify
    the router escalates to the Medium tier automatically.

3.  Send a prompt containing a customer email address. Verify the PII
    redaction engine masks the email before it reaches the LLM and
    before the response is stored in the database.

4.  Inject a prompt designed to produce unsafe content. Verify the
    Guardrails AI blocks the response, the safe fallback is returned,
    and the blocked response appears in the manager review queue.

5.  Release a blocked response from the manager queue. Verify it passes
    a second Guardrails check before being delivered.

6.  Configure a model to return malformed JSON. Verify the
    retry-with-simplified-prompt logic fires, and if that also fails,
    the template fallback is returned.

7.  Change the confidence threshold for Company A to 60 and Company B
    to 75. Verify each company uses its own threshold independently.

8.  Submit 49 mistake reports for a model. Verify it remains active.
    Submit the 50th and verify it is automatically flagged for
    retraining and removed from rotation.

**BC-008: State Management (GSD Engine)**

**Purpose**

This building code prevents state loss, AI hallucinations caused by
stale context, and context window overflow in the GSD (Guided Support
Dialogue) conversational engine. The GSD engine maintains a persistent
conversation state that tracks user intent, collected information,
pending actions, and conversation history. If this state is lost due to
a Redis restart or application crash, the AI loses all context and may
hallucinate responses or repeat questions already answered. If the
context grows too large, it can exceed the model\'s token limit, causing
truncation or API errors. This code mandates a dual-storage state
architecture with automatic recovery and proactive context management.

**When to Apply**

All features that maintain conversational state in the GSD engine must
comply with this building code. This includes: the main conversational
AI flow, multi-turn ticket resolution dialogs, information collection
sequences, handoff protocols between AI and human agents, and any
feature that relies on persistent session state. Any new conversational
flow or state-dependent feature must implement the dual-storage and
context health monitoring patterns described in this code.

**Mandatory Rules**

1.  GSD state MUST be stored in Redis as the primary store for
    performance, with a PostgreSQL sessions table as the persistent
    fallback. Every state update MUST write to both stores atomically.

2.  On Redis restart, the system MUST recover active session states from
    the PostgreSQL fallback. A recovery task MUST run on application
    startup to hydrate Redis from PostgreSQL for all sessions updated
    within the last 2 hours.

3.  Context health MUST be monitored using three thresholds: 70%
    capacity triggers a warning log, 90% capacity triggers automatic
    compression of the earliest interactions, and 95% capacity triggers
    a recommendation to the user to start a new conversation.

4.  Dynamic Context Compression MUST summarize the last 20 interactions
    when the 90% threshold is reached. The summary MUST preserve key
    facts (ticket ID, customer name, issue category, resolution status)
    and discard verbose exchanges.

5.  The GSD state JSON MUST be validated against a strict schema on
    every update. The schema MUST define required fields (session_id,
    company_id, intent, collected_info, pending_actions,
    conversation_history, context_tokens) and their types. Invalid state
    updates MUST be rejected and logged.

6.  Session timeout MUST be set to 2 hours of idle time. When a session
    times out, the state MUST be saved with a status of \"idle\" and the
    timestamp of last activity. If the user returns after idle timeout,
    the system MUST present a summary of the previous conversation and
    offer to continue or start fresh.

7.  The context_tokens field in the state MUST be updated on every
    interaction to accurately reflect the current token usage. This
    value is used to evaluate the context health thresholds.

8.  Conversation history MUST be stored as an array of role-content
    pairs, not a single concatenated string. Each entry MUST have a role
    (user, assistant, system) and a content field. This enables
    selective compression and accurate token counting.

**Implementation Pattern**

> \# GSD State Management Pattern (Python)
>
> class GSDStateEngine:
>
> async def update_state(self, session_id, delta):
>
> \# Fetch current state
>
> state = await self.\_load_state(session_id)
>
> \# Apply delta and validate against schema
>
> merged = {\*\*state, \*\*delta}
>
> validated = self.schema.validate(merged)
>
> if not validated.ok:
>
> logger.error(f\"Invalid state: {validated.errors}\")
>
> raise StateValidationError(validated.errors)
>
> \# Update token count
>
> validated.context_tokens = self.\_count_tokens(
>
> validated.conversation_history
>
> )
>
> \# Check context health
>
> health = self.\_check_context_health(
>
> validated.context_tokens
>
> validated.max_tokens
>
> )
>
> if health.action == \"compress\":
>
> validated = self.\_compress_context(
>
> validated
>
> keep_last=20
>
> )
>
> elif health.action == \"suggest_new\":
>
> validated.suggest_new_chat = True
>
> \# Dual write: Redis (primary) + Postgres (fallback)
>
> async with db.transaction():
>
> await redis.setex(
>
> f\"gsd:{session_id}\",
>
> 7200, \# 2h TTL
>
> json.dumps(validated)
>
> )
>
> await db.execute(
>
> \"UPDATE sessions SET state = :state, \"
>
> \"status = :status WHERE id = :sid\",
>
> {\"state\": validated, \"status\": \"active\",
>
> \"sid\": session_id}
>
> )
>
> async def \_load_state(self, session_id):
>
> \# Try Redis first, fall back to Postgres
>
> cached = await redis.get(f\"gsd:{session_id}\")
>
> if cached:
>
> return json.loads(cached)
>
> row = await db.fetch_one(
>
> \"SELECT state FROM sessions WHERE id = :sid\",
>
> {\"sid\": session_id}
>
> )
>
> if row:
>
> return row.state
>
> raise SessionNotFoundError(session_id)

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Kill the Redis process while an active GSD session is in progress.
    Verify the system recovers the full session state from PostgreSQL
    without data loss when the user sends their next message.

2.  Send 200 sequential messages in a single session to exceed the 90%
    context threshold. Verify automatic compression fires and preserves
    key facts (ticket ID, customer name, issue category).

3.  Continue sending messages after compression to reach the 95%
    threshold. Verify the system recommends starting a new conversation
    to the user.

4.  Attempt to update the GSD state with a missing required field (e.g.,
    no session_id). Verify the schema validation rejects the update and
    logs the error.

5.  Leave a session idle for 2 hours and 5 minutes. Verify the session
    is marked as \"idle\" and the user is shown a conversation summary
    on return.

6.  Restart the application server. Verify the startup recovery task
    hydrates Redis with all active sessions from PostgreSQL updated
    within the last 2 hours.

7.  Inject a conversation_history entry with an invalid role (e.g.,
    \"admin\" instead of \"user/assistant/system\"). Verify the schema
    validation rejects it.

**BC-009: Approval Workflow**

**Purpose**

This building code prevents approval fatigue from excessive human review
requests, missed approvals that block critical operations, and incorrect
automatic approvals that bypass necessary oversight. The approval
workflow governs every AI-initiated action that has business impact:
refund processing, subscription changes, account modifications, data
exports, and escalated customer interactions. Without proper
confidence-based routing, either too many items require human review
(creating bottlenecks and fatigue) or too few do (allowing erroneous
auto-actions that damage customer trust and revenue). This code
establishes a confidence-scored, tiered approval system with automatic
escalation, timeout handling, and batch processing capabilities.

**When to Apply**

Every AI-initiated action that modifies business data, processes
financial transactions, or changes customer-facing configuration must
comply with this building code. This includes: AI-recommended refunds,
AI-suggested subscription tier changes, AI-escalated tickets to human
agents, AI-proposed knowledge base articles, automated account
modifications, and any action where the AI\'s confidence level
determines whether human oversight is required.

**Mandatory Rules**

1.  Confidence-based routing: actions with confidence below 50% MUST be
    escalated to a manager for mandatory review. Actions with confidence
    between 50% and 80% MUST be routed to a human agent for standard
    approval. Actions with confidence above 80% MAY be auto-executed
    ONLY if a matching auto-approve rule exists for that action type.

2.  Batch approval processing MUST use atomic operations. When a batch
    is submitted, either all approved items execute together or none do.
    Partial batch approval MUST be handled by allowing the reviewer to
    select individual items from the batch rather than splitting the
    batch automatically.

3.  Approval timeout ladder MUST escalate unreviewed items on a fixed
    schedule: 2 hours (first reminder), 4 hours (second reminder), 8
    hours (escalate to manager), 24 hours (final reminder), 72 hours
    (auto-reject with audit log entry). The timeout clock starts from
    when the item enters the approval queue.

4.  Auto-approve rules MUST be checked for conflicts before creation. If
    two rules overlap for the same action type, the more restrictive
    rule MUST win. An auto-approve rule cannot reduce the required
    confidence threshold below the company minimum.

5.  Emergency pause MUST immediately queue all pending auto-execution
    items and halt new auto-approvals. The customer MUST see a status of
    \"under review\" for any affected actions. When the emergency pause
    is lifted, queued items MUST resume processing in FIFO order.

6.  Self-approval prohibition: no user may approve their own request. If
    the approver is the same as the requester, the system MUST
    automatically route the approval to the next available approver or
    escalate to a manager.

7.  A 30-second undo window MUST be available after any approval action
    (approve or reject). During this window, the approver can reverse
    their decision without creating a new approval request. After 30
    seconds, the action is finalized and can only be reversed through a
    new request.

8.  VIP accounts MUST always require human approval regardless of
    confidence score. The VIP flag on a company record overrides any
    auto-approve rule.

9.  Every approval action MUST be logged in the audit trail with:
    action_id, approver_id, decision (approved/rejected/escalated),
    timestamp, confidence_score, and any comments provided.

**Implementation Pattern**

> \# Approval Workflow Pattern (Python)
>
> class ApprovalEngine:
>
> def submit_action(self, company_id, action, confidence):
>
> \# Check VIP override
>
> if self.\_is_vip(company_id):
>
> route = \"human_required\"
>
> elif confidence \< 50:
>
> route = \"manager_escalation\"
>
> elif confidence \<= 80:
>
> route = \"human_agent\"
>
> elif self.\_check_auto_approve(
>
> company_id, action, confidence
>
> ):
>
> route = \"auto_execute\"
>
> else:
>
> route = \"human_agent\"
>
> approval = ApprovalRecord.create(
>
> company_id=company_id,
>
> action=action,
>
> confidence=confidence,
>
> route=route,
>
> timeout_at=self.\_calc_timeout(),
>
> status=\"pending\"
>
> )
>
> return approval
>
> def \_calc_timeout(self):
>
> \# Timeout ladder: 2h, 4h, 8h, 24h, 72h
>
> return now() + timedelta(hours=2)
>
> def approve(self, approval_id, approver_id):
>
> record = ApprovalRecord.get(approval_id)
>
> \# Self-approval check
>
> if record.requester_id == approver_id:
>
> raise SelfApprovalError(
>
> \"Cannot approve own request\"
>
> )
>
> \# Check auto-approve conflicts
>
> if record.route == \"auto_execute\":
>
> self.\_validate_auto_rule(
>
> record.company_id, record.action
>
> )
>
> \# Execute with undo window
>
> self.\_execute_with_undo(
>
> record, approver_id, undo_seconds=30
>
> )

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Submit an action with confidence 45%. Verify it is routed to manager
    escalation and not auto-executed.

2.  Submit an action with confidence 85% for a company with a matching
    auto-approve rule. Verify it executes automatically without human
    intervention.

3.  Submit an action with confidence 85% for a company WITHOUT a
    matching auto-approve rule. Verify it falls back to human agent
    review.

4.  Create two overlapping auto-approve rules where one sets confidence
    at 70% and the other at 90%. Verify the more restrictive rule (90%)
    takes precedence.

5.  Create an approval as User A and attempt to approve it as User A.
    Verify the self-approval prohibition fires and routes to another
    approver.

6.  Approve an item and within 30 seconds click undo. Verify the
    approval is reversed without requiring a new request.

7.  Mark a company as VIP. Submit an action with confidence 95%. Verify
    it still requires human approval due to VIP override.

8.  Trigger an emergency pause. Verify all auto-execution items are
    queued and customers see \"under review\" status. Lift the pause and
    verify FIFO resumption.

9.  Create an approval and wait 73 hours without reviewing. Verify the
    auto-reject fires with a proper audit log entry.

**BC-010: Data Lifecycle & Compliance**

**Purpose**

This building code prevents GDPR violations, unauthorized data
retention, and data loss during account lifecycle events. PARWA
processes personal data including customer names, email addresses, phone
numbers, ticket content, and AI interaction history. Under GDPR,
individuals have the right to data portability (data export), the right
to erasure (Right to be Forgotten), and the right to object to
processing. Additionally, when a customer cancels their subscription,
the system must handle data retention, agent deprovisioning, and
in-progress ticket resolution gracefully. This code establishes
end-to-end data lifecycle management from creation through retention and
deletion.

**When to Apply**

Every feature that creates, stores, processes, exports, or deletes
personal data must comply with this building code. This includes:
customer data storage, ticket content and metadata, knowledge base
articles containing customer information, AI training data derived from
interactions, audit trails, API access logs, and any feature that
handles personally identifiable information (PII). Account cancellation,
data export requests, and deletion requests must follow these rules
without exception.

**Mandatory Rules**

1.  Data export MUST be available via POST /api/account/export. The
    export MUST run asynchronously and produce a ZIP file containing:
    all tickets (JSON), knowledge base entries (JSON), AI training data
    (JSON), and the audit trail (JSON). The ZIP MUST be downloadable for
    7 days before automatic deletion.

2.  Subscription cancellation MUST NOT immediately terminate access. The
    subscription MUST remain active until the end of the paid billing
    period OR until the usage limit (defined in D13) is reached,
    whichever comes first.

3.  Right to be Forgotten requests MUST be processed by anonymizing all
    PII fields rather than deleting records. Email addresses, names, and
    phone numbers MUST be replaced with irreversible SHA-256 hashes. The
    audit record of the anonymization request itself MUST be preserved.

4.  Non-audit tables (tickets, knowledge base, training data) MUST be
    fully deleted 30 days after account cancellation and completion of
    the paid period. The 30-day window allows for any final billing
    reconciliation.

5.  Audit trail records MUST be retained for a minimum of 5 years
    regardless of account status. Audit records MUST NOT be subject to
    the Right to be Forgotten anonymization. Only the PII within audit
    descriptions may be anonymized; the structural record must persist.

6.  Upon subscription cancellation, all AI agents MUST be de-provisioned
    within 24 hours. In-progress tickets at the time of cancellation
    MUST be flagged with a \"cancellation_pending\" status and allowed
    48 hours for final resolution before archival.

7.  KYC (Know Your Customer) verification is explicitly skipped in v1
    per decision D1. No KYC data collection, verification, or storage
    logic should exist in the v1 codebase. This decision MUST be
    revisited before any future regulatory expansion.

8.  Data retention policies MUST be enforced by a daily Celery beat task
    that scans for records past their retention period and processes
    deletion or anonymization as appropriate.

**Implementation Pattern**

> \# Data Lifecycle Pattern (Python)
>
> class DataLifecycleManager:
>
> async def export_data(self, company_id):
>
> \# Async ZIP generation
>
> task = generate_export.delay(company_id)
>
> return {\"task_id\": task.id, \"status\": \"processing\"}
>
> async def handle_cancellation(self, company_id):
>
> sub = await db.fetch_one(
>
> \"SELECT \* FROM subscriptions \"
>
> \"WHERE company_id = :cid AND status = \'active\'\",
>
> {\"cid\": company_id}
>
> )
>
> \# Access continues until paid period ends
>
> sub.access_until = min(
>
> sub.current_period_end,
>
> sub.usage_limit_reached_at or sub.current_period_end
>
> )
>
> await db.execute(
>
> \"UPDATE subscriptions SET status = \'canceling\', \"
>
> \"access_until = :until WHERE id = :sid\",
>
> {\"until\": sub.access_until, \"sid\": sub.id}
>
> )
>
> \# Flag in-progress tickets
>
> await db.execute(
>
> \"UPDATE tickets SET status = \'cancellation_pending\' \"
>
> \"WHERE company_id = :cid AND status = \'open\'\",
>
> {\"cid\": company_id}
>
> )
>
> \# Schedule agent deprovisioning
>
> deprovision_agents.apply_async(
>
> args=\[company_id\],
>
> countdown=86400 \# 24 hours
>
> )
>
> async def right_to_be_forgotten(self, company_id):
>
> \# Anonymize PII with SHA-256 hashes
>
> tables = \[\"companies\", \"users\", \"tickets\", \"contacts\"\]
>
> pii_fields = \[\"email\", \"name\", \"phone\"\]
>
> for table in tables:
>
> for field in pii_fields:
>
> await db.execute(
>
> f\"UPDATE {table} SET {field} = \"
>
> \"SHA256({field}) WHERE company_id = :cid\",
>
> {\"cid\": company_id}
>
> )
>
> \# Log anonymization in audit trail (preserved)
>
> AuditTrail.log(
>
> company_id=company_id,
>
> action=\"right_to_be_forgotten\",
>
> timestamp=now()
>
> )

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Submit a data export request via POST /api/account/export. Verify
    the async task generates a ZIP containing tickets, knowledge base,
    training data, and audit trail in valid JSON format.

2.  Cancel a subscription mid-period. Verify the customer retains access
    until the end of the paid billing period and is not charged again.

3.  Submit a Right to be Forgotten request. Verify all PII fields
    (email, name, phone) are replaced with SHA-256 hashes and the
    original data is irrecoverable.

4.  Verify that audit trail records are NOT deleted or anonymized when a
    Right to be Forgotten request is processed. Only PII within
    descriptions should be hashed.

5.  Wait 31 days after account cancellation. Verify the daily retention
    task has deleted all records from non-audit tables (tickets,
    knowledge base, training data).

6.  Cancel a subscription with 5 open tickets. Verify all tickets are
    flagged as \"cancellation_pending\" and agents are scheduled for
    deprovisioning within 24 hours.

7.  Search the codebase for any KYC-related logic. Verify no KYC
    collection, verification, or storage code exists per decision D1.

8.  Verify the data export ZIP download link expires after 7 days and
    the file is automatically deleted from storage.

**BC-011: Authentication & Security**

**Purpose**

This building code prevents authentication bypass, session theft,
unauthorized API access, and privilege escalation in the PARWA platform.
Authentication is the first line of defense for any multi-tenant SaaS
platform. A compromised auth system exposes all customer data, enables
unauthorized financial actions, and allows attackers to impersonate
legitimate users. This code mandates JWT token management with
short-lived access tokens, mandatory MFA, scoped API key enforcement,
rate limiting differentiated by endpoint sensitivity, and tier-based
access control on every restricted endpoint.

**When to Apply**

Every endpoint in the PARWA API must comply with this building code.
This includes: all REST API routes, all WebSocket connections, all
webhook endpoints (for verification), all admin panel routes, all API
key-authenticated endpoints, and all internal service-to-service calls.
There are zero unauthenticated endpoints in production except the login,
OAuth callback, and public health check endpoints.

**Mandatory Rules**

1.  JWT token pair: access tokens MUST expire in 15 minutes. Refresh
    tokens MUST expire in 7 days and MUST be rotated on every use
    (refresh token rotation). A used refresh token MUST be immediately
    invalidated.

2.  Google OAuth is the ONLY supported authentication method per
    decision D11. Email/password login MUST NOT be implemented in v1.
    The OAuth flow MUST use OpenID Connect with PKCE to prevent
    authorization code interception.

3.  MFA MUST be enforced for all accounts after initial login. The
    primary MFA method is TOTP (Time-based One-Time Password) via
    authenticator apps. Backup codes (minimum 10) MUST be generated at
    MFA setup and stored hashed in the database.

4.  API keys MUST be scoped with one of three permission levels: read,
    write, or admin. Each API key MUST carry its scope in the key
    metadata and the scope MUST be enforced server-side on every
    request. An API key with read scope MUST NOT be able to trigger
    write operations regardless of the endpoint called.

5.  An API key MUST NOT be able to approve refunds unless it has BOTH
    write scope AND approval scope. The approval scope is a separate,
    additional scope that must be explicitly granted.

6.  Rate limiting MUST be applied differently based on endpoint
    sensitivity: IP-based rate limiting for general endpoints (100
    requests per minute per IP), per-account rate limiting for financial
    endpoints (20 requests per minute per account), and per-API-key rate
    limiting for integration endpoints (60 requests per minute per key).

7.  Maximum concurrent sessions per user MUST be capped at 5. When a 6th
    session is created, the oldest session MUST be terminated and its
    token invalidated immediately.

8.  Password requirements (for admin accounts only): minimum 8
    characters, bcrypt hashing with cost factor 12. Passwords MUST NOT
    be stored in plaintext or any reversible format. Failed login
    attempts MUST trigger progressive delays (1s, 2s, 4s, 8s, then
    lockout after 5 failures for 15 minutes).

9.  All references to legacy tier names (\"trivya\", \"mini\",
    \"junior\") in the codebase, database, API responses, and
    user-facing text MUST be replaced with the new naming convention:
    \"starter\", \"growth\", \"high\". No legacy names may appear in any
    production output.

10. Every restricted endpoint MUST be decorated with
    \@tier_required(tier_level) to enforce tier-based access control.
    The decorator MUST check the company\'s subscription tier against
    the required tier level and return HTTP 403 if the tier is
    insufficient.

11. No credentials (API keys, database passwords, OAuth secrets) MUST
    appear in source code. All credentials MUST be loaded from
    environment variables or a secrets manager (e.g., AWS Secrets
    Manager, HashiCorp Vault).

**Implementation Pattern**

> \# Auth Middleware Pattern (FastAPI)
>
> \@app.middleware(\"http\")
>
> async def auth_middleware(request, call_next):
>
> \# Skip public endpoints
>
> if request.url.path in PUBLIC_PATHS:
>
> return await call_next(request)
>
> \# Extract token (JWT or API Key)
>
> auth_header = request.headers.get(\"Authorization\")
>
> if not auth_header:
>
> raise HTTPException(401, \"No auth provided\")
>
> if auth_header.startswith(\"Bearer \"):
>
> token = auth_header\[7:\]
>
> payload = verify_jwt(token)
>
> if payload.token_type == \"access\":
>
> request.state.user = payload
>
> request.state.auth_type = \"jwt\"
>
> else:
>
> raise HTTPException(401, \"Invalid token type\")
>
> elif auth_header.startswith(\"ApiKey \"):
>
> key = auth_header\[7:\]
>
> api_key = verify_api_key(key)
>
> if not api_key:
>
> raise HTTPException(401, \"Invalid API key\")
>
> request.state.user = api_key
>
> request.state.auth_type = \"api_key\"
>
> request.state.scope = api_key.scope
>
> \# Session count check (max 5)
>
> sessions = count_active_sessions(
>
> request.state.user.id
>
> )
>
> if sessions \> 5:
>
> terminate_oldest_session(
>
> request.state.user.id
>
> )
>
> return await call_next(request)
>
> \# Tier gate decorator
>
> def tier_required(required_tier):
>
> def decorator(func):
>
> \@wraps(func)
>
> async def wrapper(\*args, \*\*kwargs):
>
> company = get_current_company()
>
> tier = get_tier_level(company.plan)
>
> if tier \< required_tier:
>
> raise HTTPException(
>
> 403,
>
> f\"Requires {required_tier} tier\"
>
> )
>
> return await func(\*args, \*\*kwargs)
>
> return wrapper
>
> return decorator

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Create a JWT access token and wait 16 minutes. Verify the token is
    rejected by the auth middleware.

2.  Use a refresh token to obtain a new access token. Verify the old
    refresh token is immediately invalidated and cannot be reused.

3.  Attempt to log in with email/password credentials. Verify the system
    rejects this with a clear error since only Google OAuth is supported
    per D11.

4.  Create an API key with read scope and attempt to execute a write
    operation (e.g., create a ticket). Verify the server rejects it with
    a scope error.

5.  Create an API key with write scope but without approval scope and
    attempt to approve a refund. Verify the server rejects it.

6.  Send 101 requests per minute from a single IP to a general endpoint.
    Verify the 101st request is rate-limited.

7.  Send 21 financial requests per minute from a single account. Verify
    the 21st request is rate-limited.

8.  Create 6 concurrent sessions for a single user. Verify the oldest
    session is terminated and its token is invalidated.

9.  Attempt 5 failed login attempts in a row. Verify the account is
    locked for 15 minutes after the 5th failure.

10. Search the entire codebase for the strings \"trivya\", \"mini\", and
    \"junior\". Verify zero results in production code, database
    schemas, and API responses.

11. Call a growth-tier endpoint with a starter-tier company\'s
    credentials. Verify the \@tier_required decorator returns HTTP 403.

12. Search the codebase for hardcoded credentials (API keys, passwords,
    secrets). Verify all credentials are loaded from environment
    variables.

**BC-012: Error Handling & Resilience**

**Purpose**

This building code prevents silent failures that go undetected, cascade
failures where one service outage takes down the entire system, and
insufficient monitoring that delays incident response. PARWA integrates
with multiple external services (Paddle for billing, Twilio for
SMS/voice, Brevo for email, OpenRouter for AI, Shopify for e-commerce).
Each integration is a potential failure point. Without systematic error
handling, a single provider outage could cause ticket processing to
hang, billing to silently fail, or AI responses to disappear. This code
mandates circuit breakers, structured error logging, proactive
monitoring alerts, backup strategies, and auto-restart capabilities for
every external dependency.

**When to Apply**

Every integration point with an external service must comply with this
building code. This includes: Paddle API calls (billing, subscriptions,
refunds), Twilio API calls (SMS, voice), Brevo API calls (email,
templates), OpenRouter API calls (AI model routing), Shopify API calls
(order sync, inventory), and any future third-party integrations.
Internal services that could fail (database connections, Redis
connections, Celery workers) must also implement the resilience patterns
described here.

**Mandatory Rules**

1.  Circuit breaker pattern MUST be implemented for all external service
    calls. The circuit breaker transitions through three states: CLOSED
    (normal operation), OPEN (all calls fail fast without attempting the
    external service), and HALF_OPEN (allow one test request through to
    check if the service has recovered).

2.  Circuit breaker thresholds: 5 consecutive failures trigger OPEN
    state. After 60 seconds in OPEN state, transition to HALF_OPEN. If
    the test request in HALF_OPEN succeeds, transition back to CLOSED.
    If it fails, transition back to OPEN for another 60 seconds.

3.  The circuit breaker MUST be applied to at minimum: Paddle API,
    Twilio API, Brevo API, OpenRouter API, and Shopify API. Each service
    MUST have an independent circuit breaker instance.

4.  Every external API call MUST be wrapped in a try/except block that
    catches specific exceptions for that service. Generic catch-all
    exception handlers MUST NOT be used as the primary error handling
    strategy.

5.  All errors MUST be logged in structured JSON format with: timestamp,
    service_name, error_type, error_message, request_context (sanitized
    of PII), response_code, and traceback. Plain-text error logging MUST
    NOT be used for production errors.

6.  Five critical monitoring alerts MUST be configured and active at all
    times: (1) error rate exceeding 5% of total requests in any 5-minute
    window, (2) Celery queue depth exceeding 100 pending tasks, (3)
    PostgreSQL connection pool utilization exceeding 80%, (4) failed
    billing transactions (any occurrence), and (5) AI pause duration
    exceeding 4 hours.

7.  Daily database backups MUST be performed automatically with
    Write-Ahead Logging (WAL) enabled. Backups MUST be retained for 30
    days. Backup integrity MUST be verified weekly with a test restore
    to a staging environment.

8.  Recovery Time Objective (RTO) MUST be under 1 hour. Recovery Point
    Objective (RPO) MUST be under 1 hour. These targets MUST be
    validated quarterly with a disaster recovery drill.

9.  Application processes MUST be managed by Supervisord or systemd with
    auto-restart configuration. Any crashed worker or service MUST be
    automatically restarted within 30 seconds.

10. Health check endpoints MUST be implemented for all services: /health
    (basic liveness), /ready (readiness with dependency checks), and
    /metrics (Prometheus-compatible metrics). These endpoints MUST NOT
    require authentication.

**Implementation Pattern**

> \# Circuit Breaker Pattern (Python)
>
> class CircuitBreaker:
>
> def \_\_init\_\_(self, service_name, failure_threshold=5,
>
> recovery_timeout=60):
>
> self.service = service_name
>
> self.failure_count = 0
>
> self.state = \"CLOSED\"
>
> self.last_failure = None
>
> self.failure_threshold = failure_threshold
>
> self.recovery_timeout = recovery_timeout
>
> async def call(self, func, \*args, \*\*kwargs):
>
> if self.state == \"OPEN\":
>
> if time.time() - self.last_failure \> self.recovery_timeout:
>
> self.state = \"HALF_OPEN\"
>
> else:
>
> raise CircuitOpenError(self.service)
>
> try:
>
> result = await func(\*args, \*\*kwargs)
>
> if self.state == \"HALF_OPEN\":
>
> self.state = \"CLOSED\"
>
> self.failure_count = 0
>
> return result
>
> except SpecificServiceError as e:
>
> self.failure_count += 1
>
> self.last_failure = time.time()
>
> if self.failure_count \>= self.failure_threshold:
>
> self.state = \"OPEN\"
>
> alert_team(
>
> f\"Circuit OPEN: {self.service}\",
>
> severity=\"critical\"
>
> )
>
> log_structured_error(
>
> service=self.service,
>
> error_type=type(e).\_\_name\_\_,
>
> message=str(e),
>
> state=self.state
>
> )
>
> raise
>
> \# Per-service circuit breakers
>
> paddle_cb = CircuitBreaker(\"paddle\")
>
> twilio_cb = CircuitBreaker(\"twilio\")
>
> brevo_cb = CircuitBreaker(\"brevo\")
>
> openrouter_cb = CircuitBreaker(\"openrouter\")
>
> shopify_cb = CircuitBreaker(\"shopify\")

**Loophole Checklist**

The following scenarios MUST be tested to verify no loopholes exist in
the implementation:

1.  Trigger 5 consecutive failures on the Paddle circuit breaker. Verify
    it transitions to OPEN state and all subsequent calls fail
    immediately without attempting the Paddle API.

2.  Wait 61 seconds after the circuit opens. Verify it transitions to
    HALF_OPEN and allows one test request.

3.  Send a successful request in HALF_OPEN state. Verify the circuit
    transitions back to CLOSED and resets the failure counter.

4.  Send a failed request in HALF_OPEN state. Verify the circuit
    transitions back to OPEN for another 60 seconds.

5.  Inject a Paddle-specific exception. Verify it is caught by the
    specific exception handler and NOT by a generic catch-all.

6.  Verify all error logs are in structured JSON format containing
    timestamp, service_name, error_type, error_message, and
    response_code.

7.  Push 101 tasks to the Celery queue. Verify the queue depth alert
    fires when the 101st task is enqueued.

8.  Simulate PostgreSQL connection pool utilization at 81%. Verify the
    pool utilization alert fires.

9.  Kill a Celery worker process. Verify Supervisord/systemd restarts it
    within 30 seconds.

10. Call /health, /ready, and /metrics endpoints without authentication.
    Verify all return HTTP 200 with appropriate status information.

11. Simulate a failed billing transaction. Verify the billing failure
    alert fires immediately.

12. Pause the AI service for 4 hours and 1 minute. Verify the AI pause
    duration alert fires.

13. Perform a test database restore from the most recent backup. Verify
    the restore completes successfully and data integrity is confirmed.

---

# Locked Decisions

The following 3 decisions were made during the loophole resolution process and are now LOCKED. They cannot be changed without a formal review.

---

## LD-019: Agent Lightning Training Strategy

**Loophole:** #19 — Who runs Agent Lightning training and where?

**Decision:** Do NOT run Agent Lightning training until PARWA has paying clients.

### Phase 1 (Launch — Until 3+ Paying Clients)
- AI starts smart (via pre-trained models and knowledge base) but does NOT get smarter weekly
- The "AI gets smarter every week" promise is fulfilled manually at first (you export mistakes, run Google Colab, upload weights)
- No automated training infrastructure needed
- You personally handle: export mistakes_for_training.jsonl → open Google Colab → run fine-tuning → upload model weights to GCP Cloud Storage → activate for client
- Manageable for 3-5 clients (1-2 hours/week)

### Phase 2 (After Revenue — 3+ Clients)
- Set up centralized training on RunPod (~$50-200/month)
- Full automation: daily Celery job checks mistake count → when 50 mistakes reached, export training data → RunPod trains model → upload weights → auto-activate new model
- Weekly learning loop becomes fully automated
- You monitor training runs and quality metrics via dashboard

### Phase 3 (Scale — 50+ Clients)
- Evaluate custom training infrastructure or multiple RunPod instances
- Federated learning for cross-client intelligence (V2 feature, not built in v1)
- Distribute training load across multiple GPUs

### Why This Decision
- Clients are e-commerce store owners, not ML engineers — they can't run training themselves
- No point spending $200/month on training infrastructure before you have revenue
- Manual training for first 3 clients is fully manageable
- The "AI gets smarter every week" promise starts with manual fulfillment, scales to automated

**Locked by:** Product decision, March 2026
**Status:** FINAL

---

## LD-020: Training Threshold

**Loophole:** #20 — Training triggers at 50 or 100 mistakes?

**Decision:** **50 mistakes** triggers retraining.

### Spec
- When a client's AI accumulates 50 mistake reports (manager rejections/corrections logged in human_corrections table), the model is flagged for retraining
- This is LOCKED — no admin, no configuration, no API can change this value
- Time-based fallback: every 2 weeks regardless of mistake count, a Celery beat job evaluates whether training should be triggered
- Both triggers (50 mistakes OR 2 weeks) are checked daily by the training.check_fallback Celery beat task
- The training_runs table tracks: trigger_reason (auto_mistake_threshold / time_fallback / manual), mistake_count_at_trigger, status, dataset_size, metrics

### Why This Decision
- 50 mistakes provides faster learning loop — AI improves within days, not weeks
- 100 is too conservative — AI would stay dumb for too long during the critical early adaptation phase (weeks 1-4)
- 50 is low enough to catch problems early but high enough to avoid training on noisy single-event data
- Time-based fallback (2 weeks) ensures the AI doesn't go stale even if mistake rate is low

**Locked by:** Product decision, March 2026
**Status:** FINAL

---

## LD-022: Auto-Approve Rule Creation Flow

**Loophole:** #22 — DSPy auto-rules have no rollback or validation

**Decision:** When a client creates an auto-approve rule, Jarvis MUST show all possible consequences and require explicit confirmation before activating the rule. Client can undo/disable any rule at any time.

### Flow

```
Step 1: Client tells Jarvis "auto-approve address changes"

Step 2: Jarvis analyzes the rule and identifies ALL possible consequences:
  - What types of requests will match this rule
  - What could go wrong (fraud, wrong shipping rates, compliance issues)
  - Which existing rules might conflict
  - Historical data: how many tickets this would have matched in last 30 days
  - Risk assessment: Low / Medium / High

Step 3: Jarvis displays the confirmation screen:

  ⚠️ Auto-Approve Confirmation

  Rule: Auto-approve address changes within same country

  ⚡ What could happen:
  • Fraudulent address changes could slip through
  • Customers in different countries might get wrong shipping rates
  • Returns sent to old address if not updated in time
  • Edge case: same-day address change + refund request could create conflict

  📊 Historical data (last 30 days):
  • 47 tickets would have matched this rule
  • 3 were flagged as suspicious by the current system

  Risk Level: 🟡 Medium

  [Confirm Auto-Approve]  [Cancel]  [Customize Rule]

Step 4: If client clicks "Confirm" → rule becomes active immediately
Step 5: If client clicks "Customize" → Jarvis opens rule editor for adjustments
Step 6: If client clicks "Cancel" → rule is NOT created, conversation continues normally
Step 7: Client can disable any active rule at any time via Jarvis or Settings:
  - Jarvis: "disable auto-approve rule for address changes"
  - Settings: Settings → Approval Rules → toggle active/inactive
Step 8: Rule versioning: every rule change logged in audit_trail with before/after diff
```

### Implementation Spec
- Rule conflict detection: system checks ALL existing auto-approve rules when a new one is created
- If 2 rules match the same ticket → MORE restrictive rule wins (require human approval)
- If conflict detected → Jarvis warns client: "This rule overlaps with your existing rule [X]. Want to merge or replace?"
- Rules stored in auto_handle_rules table: company_id, rule_name, conditions (JSON), risk_level, match_count_30d, is_active, version, created_at, updated_at
- Each rule gets a unique ID and can be referenced in audit trail
- Manager can view all active rules: Jarvis → "show all my auto-approve rules"

### Why This Decision
- Puts the client in full control — they understand risks BEFORE automation runs
- No silent auto-approve that could cause financial damage
- Historical data (30 days) gives concrete, real context about the rule's impact
- Client can undo anytime → eliminates fear of automation mistakes
- Better UX than a 24-hour observation period — client can start using automation immediately after informed consent
- Conflict detection prevents contradictory rules from creating loopholes

**Locked by:** Product decision, March 2026
**Status:** FINAL

---

## Loophole Coverage Summary

| # | Loophole | Status |
|---|---|---|
| 1 | Single GCP VM SPOF | ✅ BC-012 |
| 2 | Socket.io drops on deploy | ✅ BC-005 |
| 3 | Redis no persistence | ✅ BC-004 |
| 4 | GSD state loss recovery | ✅ BC-004, BC-008 |
| 5 | OpenRouter rate limits | ✅ BC-007 |
| 6 | No DB backup strategy | ✅ BC-012 |
| 7 | No dead letter queue | ✅ BC-004 |
| 8 | Multi-tenant RLS gap | ✅ BC-001 |
| 9 | Webhook HMAC incomplete | ✅ BC-003 |
| 10 | Paddle webhook idempotency | ✅ BC-002, BC-003 |
| 11 | API key no scope | ✅ BC-011 |
| 12 | Old naming (trivya/mini) | ✅ BC-011 |
| 13 | PII before logging | ✅ BC-007 |
| 14 | Rate limit IP-only financial | ✅ BC-002 |
| 15 | Voice demo failed-payment | ✅ BC-002 |
| 16 | Overage no idempotency/cap | ✅ BC-002 |
| 17 | Downgrade no proration spec | ✅ BC-002 |
| 18 | Temporary agent no auto-expiry | ✅ BC-002 |
| 19 | Who runs Agent Lightning | ✅ **LD-019** |
| 20 | Training threshold | ✅ BC-007 + **LD-020** |
| 21 | Collective Intelligence anonymization | ✅ BC-001, BC-010 |
| 22 | DSPy rule rollback | ✅ **LD-022** |
| 23 | Hardcoded confidence thresholds | ✅ BC-007 |
| 24 | Guardrails no fallback | ✅ BC-007 |
| 25 | Invalid JSON from LLM | ✅ BC-007 |
| 26 | Peer review protocol | ✅ BC-009 |
| 27 | Cold start no knowledge gate | ✅ BC-004 |
| 28 | Email auto-reply loop | ✅ BC-006 |
| 29 | Auto-approve conflicts | ✅ BC-009 |
| 30 | Batch partial approval | ✅ BC-009 |
| 31 | Pause queue behavior | ✅ BC-009 |
| 32 | Voice demo phone before payment | ✅ BC-002 |
| 33 | Savings formula duplication | ✅ BC-012 |
| 34 | Nudge frequency cap | ✅ BC-004 |
| 35 | Help GIFs 404 | ⚠️ UI content task |
| 36 | Post-cancellation data lifecycle | ✅ BC-010 |
| 37 | GDPR vs audit trail conflict | ✅ BC-010 |
| 38 | No data export feature | ✅ BC-010 |
| 39 | KYC dummy wrapper | ✅ BC-010 |
| 40 | Old naming inconsistencies | ✅ BC-011 |
| 41 | No shared API contract | 📋 Next Phase |
| 42 | No approval SLA | ✅ BC-009 |
| 43 | No monitoring alert thresholds | ✅ BC-012 |
| 44 | Quality Coach tier gate | ✅ BC-011 |
| 45 | Model deprecation handling | ✅ BC-007 |

**42 of 45 loopholes addressed by Building Codes. 3 resolved by Locked Decisions.**

**1 remaining (#35) is a UI content task (record help GIFs before launch).**

**1 remaining (#41) is addressed in Phase 2 (Feature Specs + Connection Map).**
