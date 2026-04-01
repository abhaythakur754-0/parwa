# PARWA Feature Specs — Batch 9: Pricing Intelligence, Email Ops, Frontend & Analytics

> **14 features** across Pricing & Anti-Abuse (F-006), Email Operations (F-124, F-122), Marketing & Sales (F-001, F-005, F-008), Churn & Retention (F-026), Onboarding (F-035, F-039), Ticket Operations (F-051), AI Intelligence (F-063), Agent Lifecycle (F-073), and Analytics (F-114, F-117).
>
> **Stack:** Next.js · FastAPI · PostgreSQL + pgvector · Redis · Paddle · Brevo · Twilio · Celery · Socket.io · LiteLLM/OpenRouter

---

# F-006: Anti-Arbitrage Matrix

## Overview
Backend-driven pricing intelligence system that detects and prevents users from gaming subscription tiers by analyzing ticket volumes, usage patterns, and plan selection in real time. The system surfaces proactive upgrade nudges and overage projections *before* abuse occurs, protecting revenue integrity while maintaining a positive customer experience. This is the primary defense against Loopholes #10, #14, #15, #16, #17, #18 from the PARWA loophole registry.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/anti-arbitrage/assess` | POST | `company_id`, `assessment_period` (7d/30d/90d) | `{ risk_score: 0-100, signals: [], projections: { current_month, next_month }, recommendation }` |
| `/api/anti-arbitrage/signals` | GET | `company_id`, `type` (all/volume/usage/plan) | `{ signals: [{ id, type, severity, description, detected_at, data }] }` |
| `/api/anti-arbitrage/nudge` | GET | `company_id` | `{ nudges: [{ id, type, message, cta, dismissible }] }` |
| `/api/anti-arbitrage/nudge/{id}/dismiss` | POST | `nudge_id`, `reason` | `{ status: "dismissed" }` |
| `/api/anti-arbitrage/overage-projection` | GET | `company_id`, `months` (1-6) | `{ current_usage, projected_usage, projected_overage, overage_cost, plan_upgrade_options: [] }` |
| *(Internal Celery task)* `run_arbitrage_assessment` | — | `company_id` | Evaluates signals and updates risk score |

## DB Tables
- **`anti_arbitrage_assessments`** — `id`, `company_id`, `risk_score` SMALLINT (0-100), `signal_count` INT, `projection_monthly_tickets` INT, `projection_overage_cost` DECIMAL(10,2), `recommendation` TEXT, `assessment_period_start` DATE, `assessment_period_end` DATE, `created_at`
  - **Indexes:** `UNIQUE(company_id, assessment_period_end)`, `idx_company_id` ON `company_id`, `idx_risk_score` ON `risk_score`
- **`anti_arbitrage_signals`** — `id`, `company_id`, `assessment_id`, `signal_type` (volume_spike/usage_pattern_mismatch/plan_underuse/overage_approaching/burst_pattern/tier_gaming/sharing_suspicion), `severity` (low/medium/high/critical), `description` TEXT, `signal_data` (JSONB), `dismissed` BOOL DEFAULT false, `dismissed_by` UUID, `dismissed_at` TIMESTAMPTZ, `created_at`
  - **Indexes:** `idx_company_type` ON `(company_id, signal_type)`, `idx_severity` ON `severity`
- **`anti_arbitrage_nudges`** — `id`, `company_id`, `nudge_type` (upgrade/overage_warning/usage_tips/plan_review), `message` TEXT, `cta_text` TEXT, `cta_url` TEXT, `dismissible` BOOL, `dismissed` BOOL DEFAULT false, `dismissed_at` TIMESTAMPTZ, `expires_at` TIMESTAMPTZ, `created_at`
  - **Indexes:** `idx_company_active` ON `(company_id, dismissed, expires_at)`
- **`usage_snapshots`** — `id`, `company_id`, `snapshot_date` DATE, `total_tickets` INT, `ai_resolved_tickets` INT, `human_resolved_tickets` INT, `unique_customers` INT, `plan_limit` INT, `plan_tier` VARCHAR(50), `overage_tickets` INT, `overage_cost` DECIMAL(10,2), `created_at`
  - **Indexes:** `UNIQUE(company_id, snapshot_date)`, `idx_company_date` ON `(company_id, snapshot_date)`

## BC Rules
- **BC-002** (Financial Actions): All monetary values (`overage_cost`, `projected_overage`) use DECIMAL(10,2). Overage projections are calculated with the `decimal` module — no float arithmetic. All pricing calculations logged in `audit_trail` with `action_type="arbitrage_assessment"`.
- **BC-002** Rule 7 (Idempotency): Daily overage charges include idempotency check on `(date + company_id)`. The anti-arbitrage system pre-calculates expected overage before Paddle charges fire.
- **BC-001** (Multi-Tenant Isolation): All assessments, signals, and usage snapshots scoped by `company_id`. No cross-tenant usage comparison or data leakage.
- **BC-012** (Error Handling): If an assessment task fails, last known risk score is retained; circuit breaker prevents cascading failures during assessment runs.
- **BC-004** (Background Jobs): Assessment runs as a scheduled Celery beat task (daily at 02:00 UTC) with `company_id` first param, `max_retries=3`, exponential backoff. DLQ for permanently failed assessments.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Tenant rapidly cycles between plans (upgrade → downgrade → upgrade weekly) | Signal type `tier_gaming` triggered; plan change history analyzed; if > 3 cycles in 90 days, risk score +30; upgrade nudge includes a "minimum commitment" recommendation |
| Ticket volume tripled overnight (legitimate marketing campaign) | `volume_spike` signal fired with severity based on historical baseline; system checks for marketing calendar integration or webhook signals; if legitimate, signal is auto-dismissed with `reason="confirmed_campaign"` |
| Multiple users from different IPs share the same account | `sharing_suspicion` signal triggered when concurrent sessions > 5 or IP geolocations span > 3 time zones in a 24h period; BC-011 Rule 6 enforced (max 5 sessions) |
| Tenant is on free trial and approaching plan limits within 3 days | `overage_approaching` signal with `severity=critical`; in-app notification + email via Brevo (template: `trial_limit_warning`); no upgrade nudge shown during trial — conversion nudge shown instead |
| Overage projection shows negative cost (under-plan usage) | System recalculates; if usage < 60% of plan limit for 30 consecutive days, signal `plan_underuse` triggered with suggestion to downgrade; BC-002 Rule 10 (proration delegated to Paddle) |

## Acceptance Criteria
1. **Given** a tenant on the Starter plan (500 tickets/month) **When** they exceed 400 tickets by day 20 of their billing cycle **Then** the anti-arbitrage system fires a `high` severity `overage_approaching` signal and surfaces a nudge with projected overage cost and upgrade CTA.
2. **Given** a tenant with a `risk_score` above 75 **When** the daily assessment task runs **Then** an alert is sent to the operations team and a `plan_review` nudge is displayed on the tenant's billing dashboard that is not dismissible.
3. **Given** multiple usage snapshots over 90 days **When** the assessment endpoint is called **Then** the response includes accurate overage projections for the next 3 months using DECIMAL(10,2) calculations with no float drift, and the `audit_trail` logs the assessment action.
4. **Given** a tenant dismisses a nudge **When** the same signal type is re-detected within 7 days **Then** the nudge is NOT re-surfaced (7-day cooldown); after cooldown, if signal persists, the nudge reappears with an incremented priority counter.

---

# F-124: Bounce & Complaint Handling

## Overview
Handles email bounces (soft and hard) and spam complaints from email providers (Gmail, Outlook, Yahoo) by processing bounce webhooks from Brevo, updating customer email status to prevent sending to invalid addresses, and alerting tenants when their email deliverability is at risk. This is the primary defense against sender reputation damage and implements BC-006 rule 8.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/webhooks/brevo/bounce` | POST | Raw Brevo webhook payload + headers | `{ status: "accepted" }` (async processing) |
| `/api/webhooks/brevo/complaint` | POST | Raw Brevo webhook payload + headers | `{ status: "accepted" }` (async processing) |
| `/api/email/bounces` | GET | `company_id`, `status` (all/soft/hard/complaint), `from`, `to` | `{ bounces: [{ id, email, type, reason, provider, event_date, status, ticket_count }] }` |
| `/api/email/bounces/{id}/whitelist` | POST | `bounce_id`, `justification` | `{ status: "whitelisted" }` |
| `/api/email/bounces/stats` | GET | `company_id`, `range` (7d/30d/90d) | `{ total_bounces, hard_bounces, soft_bounces, complaints, bounce_rate, complaint_rate, trend }` |
| `/api/email/bounces/digest` | GET | `company_id` | `{ since_last_digest, critical_alerts, summary }` |
| *(Internal Celery task)* `process_bounce_event` | — | `company_id`, `event_id`, `event_data` | Updates email status, suppresses sending, notifies tenant |

## DB Tables
- **`email_bounces`** — `id`, `company_id`, `customer_email` VARCHAR(255), `bounce_type` (soft/hard/complaint/unsubscribe), `bounce_reason` TEXT, `provider` VARCHAR(50) (gmail/outlook/yahoo/other), `provider_code` VARCHAR(20), `event_id` VARCHAR(255) UNIQUE, `related_ticket_id` UUID, `email_status_before` VARCHAR(20), `email_status_after` VARCHAR(20), `whitelisted` BOOL DEFAULT false, `whitelist_justification` TEXT, `whitelisted_by` UUID, `whitelisted_at` TIMESTAMPTZ, `created_at`
  - **Indexes:** `UNIQUE(event_id)`, `idx_company_email` ON `(company_id, customer_email)`, `idx_bounce_type` ON `bounce_type`, `idx_created_at` ON `created_at`
- **`customer_email_status`** — `id`, `company_id`, `customer_email` VARCHAR(255), `email_status` (active/soft_bounced/hard_bounced/complained/suppressed), `bounce_count` INT DEFAULT 0, `complaint_count` INT DEFAULT 0, `last_bounce_at` TIMESTAMPTZ, `last_complaint_at` TIMESTAMPTZ, `suppressed_at` TIMESTAMPTZ, `whitelisted` BOOL DEFAULT false, `updated_at`
  - **Indexes:** `UNIQUE(company_id, customer_email)`, `idx_email_status` ON `(company_id, email_status)`
- **`email_deliverability_alerts`** — `id`, `company_id`, `alert_type` (bounce_spike/complaint_spike/blacklist_risk/reputation_warning), `severity` (low/medium/high/critical), `message` TEXT, `metric_value` DECIMAL(5,4), `threshold` DECIMAL(5,4), `acknowledged` BOOL DEFAULT false, `acknowledged_by` UUID, `created_at`
  - **Indexes:** `idx_company_active` ON `(company_id, acknowledged, created_at)`

## BC Rules
- **BC-003** (Webhook Handling): Brevo bounce/complaint webhooks verified via IP allowlist (BC-003 rule 5). HMAC verification where supported. Idempotency via `event_id` UNIQUE constraint on `email_bounces` table. Async processing via Celery — HTTP 200 returned within 3 seconds. Failed processing retries 3x with exponential backoff (60s, 300s, 900s).
- **BC-006** Rule 8: Bounce and complaint events update customer email status to `invalid` (hard bounce/complaint) or `soft_bounced` (soft bounce). All events notify the account manager via in-app alert and Brevo email (template: `deliverability_alert`).
- **BC-001** (Multi-Tenant Isolation): All bounce data scoped by `company_id`. Brevo webhook payload must include or resolve to a `company_id` via the customer email lookup.
- **BC-004** (Background Jobs): Bounce event processing runs as a Celery task with `company_id` first param. Deliverability digest computation runs daily as a beat task. All tasks have `max_retries=3`.
- **BC-012** (Error Handling): If a bounce cannot be matched to a customer record, event is logged but does not block processing. Webhook processing failures are routed to DLQ with ops alert.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Hard bounce on a customer email that has 5 open tickets | Email status set to `hard_bounced`; all open tickets flagged with `customer_email_invalid=true`; assigned agents notified via Socket.io; no new automated emails sent; agent can still reply via other channels |
| Same email soft-bounces 3 times in 7 days | Status escalated from `soft_bounced` to `suppressed` automatically; customer record updated; tenant notified; email removed from all outbound campaigns |
| Brevo sends duplicate bounce webhooks (same event_id) | Idempotency check via UNIQUE constraint on `event_id`; second delivery returns 200 with `already_processed` status; no duplicate records created |
| Customer email is whitelisted but receives a hard bounce | Whitelist is NOT auto-removed; a new `hard_bounced` status record is created; alert sent to the whitelisting admin with recommendation to review the whitelist decision |
| Complaint from Gmail (spam report) | Status set to `complained`; email permanently suppressed regardless of whitelist; tenant notified with severity `critical`; Gmail-specific complaint rate tracked; if > 0.1% complaint rate, system-wide alert to ops team for sender reputation risk |
| Bulk bounce event (e.g., 500 bounces from a single campaign) | Each bounce processed individually as Celery tasks; deliverability spike alert triggered with `severity=critical`; rate limiting on Brevo webhook endpoint prevents flooding (BC-003 rule 11) |

## Acceptance Criteria
1. **Given** a Brevo bounce webhook for a hard bounce on `jane@example.com` belonging to tenant ABC **When** the webhook is received **Then** the `customer_email_status` is updated to `hard_bounced`, all future automated emails to that address are suppressed, and tenant ABC receives an in-app alert within 60 seconds via Socket.io.
2. **Given** a Brevo complaint webhook from Gmail reporting a spam complaint **When** the webhook is processed **Then** the customer email is set to `complained` (permanent suppression), the complaint is logged in `email_bounces`, and the tenant's deliverability alert dashboard shows a `critical` alert with the complaint rate metrics.
3. **Given** a duplicate Brevo webhook with the same `event_id` **When** the webhook is received a second time **Then** the system returns HTTP 200 with `status: "accepted"` and the idempotency check prevents any duplicate database writes or customer status changes.
4. **Given** a tenant admin whitelists a previously bounced email **When** the email later receives another hard bounce **Then** the whitelist is preserved, a new bounce record is created, and the admin is notified with a recommendation to review the whitelist decision, but sending is NOT auto-resumed without explicit admin confirmation.

---

# F-001: Landing Page with Industry Selector

## Overview
Dynamic marketing landing page featuring an interactive industry selector dropdown that instantly tailors hero copy, testimonials, use-case examples, feature highlights, and pricing previews to the visitor's vertical (e-commerce, SaaS, healthcare, fintech, education, real estate, logistics). This is a Next.js frontend feature with a FastAPI backend serving industry-specific content configurations.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/landing/industries` | GET | — | `{ industries: [{ id, name, icon, slug, tagline }] }` |
| `/api/landing/content/{industry_slug}` | GET | `industry_slug` | `{ hero: {}, testimonials: [], use_cases: [], features: [], pricing_preview: {}, faq: [], stats: {} }` |
| `/api/landing/content/default` | GET | — | `{ hero: {}, testimonials: [], ... }` (generic content when no industry selected) |
| `/api/landing/analytics` | POST | `visitor_id`, `industry_slug`, `action` (select/scroll/click/demo_request), `referrer` | `{ status: "recorded" }` |
| `/api/landing/demo-request` | POST | `name`, `email`, `company`, `industry_slug`, `message` | `{ request_id, status: "submitted" }` |

## DB Tables
- **`landing_industries`** — `id`, `slug` VARCHAR(50) UNIQUE, `name` VARCHAR(100), `icon_url` TEXT, `tagline` TEXT, `hero_title` TEXT, `hero_subtitle` TEXT, `hero_cta` TEXT, `hero_image_url` TEXT, `stats` (JSONB — e.g., `{"resolution_rate": 94, "avg_response_time": "30s"}`), `sort_order` INT, `active` BOOL DEFAULT true, `created_at`, `updated_at`
  - **Indexes:** `UNIQUE(slug)`, `idx_active_order` ON `(active, sort_order)`
- **`landing_testimonials`** — `id`, `industry_slug` VARCHAR(50) (nullable — generic testimonials), `company_name` VARCHAR(255), `person_name` VARCHAR(255), `person_title` VARCHAR(255), `quote` TEXT, `avatar_url` TEXT, `rating` SMALLINT (1-5), `featured` BOOL DEFAULT false, `sort_order` INT, `created_at`
  - **Indexes:** `idx_industry` ON `industry_slug`, `idx_featured` ON `(featured, sort_order)`
- **`landing_use_cases`** — `id`, `industry_slug` VARCHAR(50), `title` TEXT, `description` TEXT, `icon_url` TEXT, `before_scenario` TEXT, `after_scenario` TEXT, `sort_order` INT, `created_at`
  - **Indexes:** `idx_industry` ON `industry_slug`
- **`landing_page_analytics`** — `id`, `visitor_id` UUID, `session_id` UUID, `industry_slug` VARCHAR(50), `action` VARCHAR(50), `referrer_domain` VARCHAR(255), `user_agent` TEXT, `country_code` VARCHAR(3), `created_at`
  - **Indexes:** `idx_visitor` ON `visitor_id`, `idx_industry_action` ON `(industry_slug, action)`, `idx_created_at` ON `created_at`
- **`demo_requests`** — `id`, `name` VARCHAR(255), `email` VARCHAR(255), `company` VARCHAR(255), `industry_slug` VARCHAR(50), `message` TEXT, `status` (new/contacted/qualified/converted/rejected), `utm_source` VARCHAR(100), `utm_medium` VARCHAR(100), `utm_campaign` VARCHAR(100), `created_at`
  - **Indexes:** `idx_email` ON `email`, `idx_status` ON `status`, `idx_created_at` ON `created_at`

## BC Rules
- **BC-001** (Multi-Tenant Isolation): Landing page content is NOT tenant-scoped — it serves anonymous visitors. However, `demo_requests` are scoped by the sales pipeline (not company_id since visitors are pre-signup). Landing analytics are aggregated globally with industry breakdown.
- **BC-012** (Error Handling): If an industry slug is not found, return default/generic content rather than a 404. Landing page must always render — never show error states to anonymous visitors. Circuit breaker on content API; fallback to hardcoded default content if API is unreachable.
- **BC-006** (Email): Demo requests trigger a Brevo email (template: `demo_request_confirmation`) to the visitor. Internal notification sent to sales team via Brevo (template: `new_demo_request`).
- **BC-010** (Data Lifecycle): Landing page analytics (visitor actions) are GDPR-light — no PII required beyond optional cookies. Demo request data subject to standard retention and right-to-erasure policies.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Visitor navigates directly to `/industry/fintech` URL without using dropdown | Backend resolves slug and returns fintech-specific content; URL is canonical for SEO; dropdown auto-selects "Fintech" |
| Selected industry has no testimonials configured | System falls back to 3 generic testimonials (cross-industry); frontend shows these with a note "Results across all industries" |
| Industry selector dropdown is loaded before API responds | Dropdown renders with skeleton/shimmer state; previous content remains visible until new content loads (no blank flash) |
| Visitor selects industry, scrolls, then switches industry mid-page | Content swaps immediately with a subtle fade transition; scroll position resets to top; analytics logs both selections |
| Bot/crawler hits the landing page with thousands of requests | Rate limiting applied (100 req/min per IP); bot detection via user-agent check; analytics events from known bots are filtered out |
| Demo request submitted with invalid email format | Frontend validates email format before submission; backend re-validates and returns 422 with clear error message; CAPTCHA (reCAPTCHA v3) validates human interaction |

## Acceptance Criteria
1. **Given** a visitor lands on the PARWA homepage **When** they select "E-commerce" from the industry dropdown **Then** the hero section, testimonials, use cases, and feature highlights update within 500ms to display e-commerce-specific content with relevant imagery and copy.
2. **Given** an industry slug that does not exist in the database **When** the `/api/landing/content/{slug}` endpoint is called **Then** the API returns HTTP 200 with default/generic content and the frontend displays this gracefully without error states or broken layouts.
3. **Given** a visitor submits a demo request with valid data **When** the form is submitted **Then** a confirmation email is sent via Brevo to the visitor (template: `demo_request_confirmation`), a notification is sent to the sales team, and the request is stored in `demo_requests` with UTM tracking parameters if present.
4. **Given** a visitor interacts with the landing page (selects industry, scrolls sections, clicks CTA) **When** analytics events are fired **Then** each interaction is logged in `landing_page_analytics` with visitor_id, industry_slug, action, and timestamp, and the data is available for aggregation within 5 minutes.

---

# F-005: Smart Bundle Visualizer

## Overview
Interactive pricing page tool that allows prospects and existing tenants to dynamically build custom bundles by toggling add-on modules (voice AI, multilingual support, advanced analytics, custom integrations, priority support). The visualizer instantly recalculates total monthly cost, shows savings from bundling, and produces a configuration ready for checkout via Paddle.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/pricing/bundles` | GET | `plan_tier` (starter/growth/enterprise) | `{ base_plan: { price, features }, add_ons: [{ id, name, price, description, category }] }` |
| `/api/pricing/bundles/calculate` | POST | `plan_tier`, `billing_cycle` (monthly/annual), `add_ons[]` | `{ base_price, add_on_total, bundle_discount_pct, total_monthly, total_annual, savings_vs_individual }` |
| `/api/pricing/bundles/save` | POST | `company_id`, `plan_tier`, `add_ons[]`, `billing_cycle` | `{ bundle_id, status: "saved" }` |
| `/api/pricing/bundles/{id}` | GET | `bundle_id` | `{ bundle_id, plan_tier, add_ons, total, status }` |
| `/api/pricing/bundles/checkout` | POST | `bundle_id`, `company_id` | `{ paddle_checkout_url, paddle_subscription_id }` |
| `/api/pricing/add-ons` | GET | `category` (optional) | `{ add_ons: [{ id, name, price_monthly, price_annual, description, category, features, popular }] }` |

## DB Tables
- **`pricing_add_ons`** — `id`, `name` VARCHAR(100), `slug` VARCHAR(50) UNIQUE, `description` TEXT, `category` (ai_analytics/communications/integrations/support/security), `price_monthly` DECIMAL(10,2), `price_annual` DECIMAL(10,2), `features` (JSONB), `popular` BOOL DEFAULT false, `sort_order` INT, `active` BOOL DEFAULT true, `created_at`, `updated_at`
  - **Indexes:** `UNIQUE(slug)`, `idx_category_active` ON `(category, active, sort_order)`
- **`pricing_bundle_discounts`** — `id`, `add_on_count_min` INT, `add_on_count_max` INT, `discount_pct` DECIMAL(5,2), `description` TEXT, `active` BOOL DEFAULT true, `created_at`
  - **Indexes:** `idx_count_range` ON `(add_on_count_min, add_on_count_max, active)`
- **`saved_bundles`** — `id`, `company_id`, `plan_tier` VARCHAR(50), `billing_cycle` (monthly/annual), `add_ons` (JSONB — array of add_on IDs with quantities), `base_price` DECIMAL(10,2), `add_ons_total` DECIMAL(10,2), `bundle_discount_pct` DECIMAL(5,2), `total_monthly` DECIMAL(10,2), `total_annual` DECIMAL(10,2), `paddle_checkout_id` VARCHAR(255), `status` (draft/pending/active/expired), `created_at`, `updated_at`
  - **Indexes:** `idx_company` ON `company_id`, `idx_status` ON `status`
- **`pricing_tiers`** — `id`, `tier_name` VARCHAR(50), `price_monthly` DECIMAL(10,2), `price_annual` DECIMAL(10,2), `ticket_limit` INT, `features` (JSONB), `sort_order` INT, `active` BOOL DEFAULT true, `created_at`, `updated_at`
  - **Indexes:** `UNIQUE(tier_name)`, `idx_active_order` ON `(active, sort_order)`

## BC Rules
- **BC-002** (Financial Actions): All prices stored as DECIMAL(10,2). Bundle calculation uses Python `decimal.Decimal` module — zero float arithmetic. Checkout delegated to Paddle API; PARWA never handles credit card data directly. Bundle save creates an approval record for financial audit.
- **BC-002** Rule 2 (Idempotency): Paddle checkout creation uses `bundle_id` as idempotency key to prevent duplicate subscriptions.
- **BC-001** (Multi-Tenant Isolation): Saved bundles scoped by `company_id`. Pricing configuration (add-ons, tiers, discounts) is global but calculated per-tenant.
- **BC-012** (Error Handling): If Paddle API is unavailable during checkout, error is surfaced with a "Try again" CTA; bundle draft is preserved. Circuit breaker on Paddle API calls.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Annual billing selected with 6+ add-ons | Bundle discount applied (e.g., 15% off for 4+ add-ons, 20% for 6+); discount tiers configurable via `pricing_bundle_discounts` table; total displayed with savings callout |
| Add-on is deactivated while a saved bundle references it | Bundle still renders with the add-on shown as "No longer available" (greyed out); recalculation excludes its price; notification shown to update the bundle |
| Visitor toggles add-ons rapidly (debounce scenario) | Frontend debounces calculation calls (300ms); intermediate toggles don't fire API calls; only final state triggers recalculation |
| Enterprise tier selected but add-on already included in base plan | Add-on shown as "Included" (disabled toggle, checkmark icon); not counted toward add-on pricing or bundle discount calculation |
| Currency display for international visitors | All prices displayed in USD; currency selector is a future feature; disclaimer shown: "All prices in USD. Local currency billing available after signup." |

## Acceptance Criteria
1. **Given** a visitor is on the pricing page **When** they toggle 3 add-ons (Voice AI, Advanced Analytics, Priority Support) on the Growth plan with annual billing **Then** the total recalculates instantly showing base plan price + add-on prices - bundle discount, with a clear savings callout compared to monthly billing.
2. **Given** a visitor configures a bundle and clicks "Save & Continue" **When** the save endpoint is called **Then** the bundle configuration is stored in `saved_bundles` with all prices as DECIMAL(10,2), and the response includes a `bundle_id` for later checkout.
3. **Given** a saved bundle with bundle_id **When** the checkout endpoint is called **Then** a Paddle checkout URL is generated with idempotency protection (bundle_id as key), and the response redirects the user to Paddle's hosted checkout with pre-populated line items.
4. **Given** an add-on's price changes in the database **When** a previously saved bundle (draft status) is viewed **Then** the bundle recalculates with current pricing and shows a "Prices updated since last save" notification, but does NOT auto-charge the difference.

---

# F-008: Voice Demo Paywall ($1)

## Overview
Gated demo experience where unauthenticated visitors pay $1 via Stripe to test PARWA's voice AI capabilities with a 3-minute interactive call. This feature collects payment upfront, provisions a temporary voice demo session, connects the visitor to a Twilio-powered voice AI agent, and automatically terminates after the demo duration. Per BC-002 rule 12, phone number collection occurs ONLY after payment confirmation.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/voice-demo/initiate` | POST | `email` | `{ session_id, stripe_checkout_url }` |
| `/api/voice-demo/confirm` | POST | `session_id`, `stripe_session_id` | `{ status: "payment_confirmed", phone_input_url }` |
| `/api/voice-demo/submit-phone` | POST | `session_id`, `phone_number` | `{ status: "ready", twilio_call_sid: null }` |
| `/api/voice-demo/start-call` | POST | `session_id` | `{ status: "calling", estimated_wait_seconds }` |
| `/api/voice-demo/status/{session_id}` | GET | `session_id` | `{ status, duration_remaining, transcript_preview[] }` |
| `/api/webhooks/stripe/voice-demo` | POST | Stripe webhook payload + signature | `{ status: "received" }` (async) |

## DB Tables
- **`voice_demo_sessions`** — `id`, `session_id` UUID UNIQUE, `email` VARCHAR(255), `stripe_session_id` VARCHAR(255) UNIQUE, `payment_status` (pending/confirmed/refunded/failed), `amount_paid` DECIMAL(10,2) DEFAULT 1.00, `currency` VARCHAR(3) DEFAULT 'USD', `phone_number` VARCHAR(30), `phone_collected_at` TIMESTAMPTZ, `twilio_call_sid` VARCHAR(255), `call_status` (pending/active/completed/failed/terminated), `demo_duration_seconds` INT DEFAULT 180, `actual_duration_seconds` INT, `transcript` TEXT, `recording_url` TEXT, `created_at`, `expires_at`, `started_at`, `ended_at`
  - **Indexes:** `UNIQUE(session_id)`, `UNIQUE(stripe_session_id)`, `idx_email` ON `email`, `idx_payment_status` ON `payment_status`, `idx_created_at` ON `created_at`
- **`voice_demo_payments`** — `id`, `session_id` UUID REFERENCES `voice_demo_sessions(id)`, `stripe_payment_intent_id` VARCHAR(255) UNIQUE, `amount` DECIMAL(10,2), `currency` VARCHAR(3), `status` (pending/succeeded/failed/refunded), `stripe_webhook_event_id` VARCHAR(255), `refunded_at` TIMESTAMPTZ, `refund_reason` TEXT, `created_at`
  - **Indexes:** `UNIQUE(stripe_payment_intent_id)`, `idx_session` ON `session_id`, `idx_status` ON `status`
- **`voice_demo_analytics`** — `id`, `session_id` UUID, `event_type` (initiated/payment_confirmed/call_started/call_ended/demo_expired/refunded), `event_data` (JSONB), `created_at`
  - **Indexes:** `idx_session` ON `session_id`, `idx_event_type` ON `event_type`

## BC Rules
- **BC-002** (Financial Actions): All monetary amounts use DECIMAL(10,2). Payment amount hardcoded to $1.00 — not configurable via API. Stripe webhook processing includes idempotency check on `stripe_webhook_event_id`. Payment confirmation creates an approval record in `audit_trail`.
- **BC-002** Rule 12: Phone number is collected ONLY after payment status is `confirmed`. If payment fails or times out, any partially entered phone data is cleared. The `/submit-phone` endpoint rejects requests where `payment_status != confirmed`.
- **BC-003** (Webhook Handling): Stripe webhook signature verified using `stripe.webhooks.constructEvent()`. Idempotency via `stripe_webhook_event_id` UNIQUE constraint. Async processing via Celery. Response within 3 seconds.
- **BC-012** (Error Handling): If Twilio call fails to connect, session status set to `failed` and automatic refund initiated via Stripe API. If demo expires before phone submission, session marked `expired` and no charge is applied (pre-auth only).
- **BC-010** (Data Lifecycle): Demo session data (transcript, recording) retained for 30 days then auto-deleted. Email and phone number NOT used for marketing without explicit consent checkbox.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Visitor initiates payment but abandons before completing | Session expires after 30 minutes (configurable); Stripe checkout session auto-expires; no charge applied; analytics event logged as `demo_expired` |
| Payment succeeds but Twilio is unable to connect the call | Automatic refund triggered via Stripe API within 60 seconds; user notified via email; session marked as `failed` with reason `twilio_connection_error` |
| Visitor provides an invalid phone number | Twilio validates phone format during `/start-call`; invalid numbers return 422 with clear error; visitor can re-submit without re-payment (session remains `confirmed`) |
| Demo call exceeds 3-minute duration | Twilio call is programmatically terminated; session status set to `completed`; `actual_duration_seconds` recorded; no additional charges |
| Visitor requests a refund after the demo | Refund processed via Stripe within 24 hours; `refund_reason` logged; session status updated to `refunded`; $1 refund is non-negotiable per policy |
| Same email attempts multiple demo sessions | Email is tracked; second attempt within 7 days shows "You've already tried the demo. Contact sales@parwa.ai for an extended trial." — prevents $1 farming |

## Acceptance Criteria
1. **Given** an unauthenticated visitor initiates a voice demo **When** they complete the $1 Stripe payment **Then** the `payment_status` is updated to `confirmed`, the phone number input form is displayed, and the visitor's email and session data are stored with all monetary values as DECIMAL(10,2).
2. **Given** a confirmed demo session **When** the visitor submits a valid phone number and clicks "Start Demo" **Then** a Twilio call is initiated to the provided number, connected to a PARWA voice AI agent, and the call is automatically terminated after 180 seconds.
3. **Given** a payment failure (card declined) **When** the Stripe webhook reports `payment_intent.payment_failed` **Then** the session status is set to `failed`, no phone number is stored or requested, and the visitor sees a clear "Payment failed. Please try again." message.
4. **Given** a visitor who already completed a demo within the last 7 days **When** they attempt to initiate another demo **Then** the system returns a 429 response with a message directing them to contact sales, and no Stripe checkout session is created.

---

# F-026: Cancellation Request Tracking

## Overview
Backend tracking system that logs every cancellation request with reason taxonomy, retention offer details, customer interactions, and final outcome for comprehensive churn analysis. This system provides the data foundation for understanding why customers leave, which retention offers work, and predictive churn modeling.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/cancellations` | POST | `company_id`, `reason_category`, `reason_detail`, `feedback` | `{ cancellation_id, status: "open" }` |
| `/api/cancellations/{id}` | GET | `cancellation_id` | `{ cancellation, retention_offers, interactions, outcome }` |
| `/api/cancellations/{id}/retention-offer` | POST | `cancellation_id`, `offer_type`, `offer_details` (JSONB) | `{ offer_id, status: "proposed" }` |
| `/api/cancellations/{id}/respond` | POST | `cancellation_id`, `response` (accept_offer/decline/proceed) | `{ status: "updated" }` |
| `/api/cancellations/{id}/complete` | POST | `cancellation_id`, `final_outcome` | `{ status: "completed" }` |
| `/api/cancellations/analytics` | GET | `range` (30d/90d/6m/1y) | `{ total_requests, save_rate, top_reasons, avg_time_to_resolution, retention_offer_effectiveness }` |

## DB Tables
- **`cancellation_requests`** — `id`, `company_id`, `reason_category` (price/competition/features/support/technical/other), `reason_detail` TEXT, `feedback` TEXT, `requested_by` UUID, `requested_at` TIMESTAMPTZ, `status` (open/in_retention/offer_accepted/offer_declined/proceeding/completed/withdrawn), `assigned_to` UUID, `outcome` (cancelled/downgraded/saved/still_deciding), `outcome_detail` TEXT, `completed_at` TIMESTAMPTZ, `created_at`
  - **Indexes:** `idx_company` ON `company_id`, `idx_status` ON `status`, `idx_reason` ON `reason_category`, `idx_created_at` ON `created_at`
- **`retention_offers`** — `id`, `cancellation_id` UUID REFERENCES `cancellation_requests(id)`, `offer_type` (discount/feature_upgrade/extension/custom_plan/freeze), `offer_details` (JSONB — e.g., `{"discount_pct": 20, "duration_months": 3}`), `proposed_by` UUID, `proposed_at` TIMESTAMPTZ, `response` (pending/accepted/declined), `responded_at` TIMESTAMPTZ, `created_at`
  - **Indexes:** `idx_cancellation` ON `cancellation_id`, `idx_offer_type` ON `offer_type`
- **`cancellation_interactions`** — `id`, `cancellation_id` UUID REFERENCES `cancellation_requests(id)`, `interaction_type` (email/call/chat/survey), `channel` VARCHAR(50), `summary` TEXT, `agent_id` UUID, `created_at`
  - **Indexes:** `idx_cancellation` ON `cancellation_id`, `idx_created_at` ON `created_at`

## BC Rules
- **BC-002** (Financial Actions): Retention offers involving discounts or credits use DECIMAL(10,2). Any financial retention offer (discount, credit, refund) creates an approval record in `audit_trail`. Offer acceptance triggers Paddle subscription modification via their API.
- **BC-009** (Approval Workflow): Retention offers exceeding $50/month in discount value require supervisor approval. Approval record created with `action_type="retention_offer"` and all offer details. Jarvis consequences display shows projected revenue impact before approval.
- **BC-001** (Multi-Tenant Isolation): All cancellation data scoped by `company_id`. Analytics endpoint aggregates per-tenant only; cross-tenant churn comparison is admin-only.
- **BC-012** (Error Handling): If a cancellation request cannot be matched to a company, the request is rejected with a clear error. Retention offer application failure does not block the cancellation flow — the customer can still proceed with cancellation.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Customer requests cancellation but their subscription is already expired | System detects expired subscription and returns clear message "Subscription already expired." Cancellation request is still logged for analytics but marked as `outcome=already_expired` |
| Customer accepts a retention offer but then requests cancellation again within 30 days | Second cancellation tracked separately; linked to the first via `previous_cancellation_id`; analytics flags repeat cancellations as high-churn-risk signal |
| Retention offer includes a discount that requires Paddle modification | Offer status set to `pending_paddle_update`; Paddle API called asynchronously; if Paddle fails, offer is rolled back and customer notified; BC-002 Rule 6 (compensation transaction) applies |
| Customer cancels but has active tickets assigned to their workspace | Cancellation does NOT immediately terminate access; 30-day grace period applies; during grace period, tickets remain accessible; auto-export of ticket data offered via email |

## Acceptance Criteria
1. **Given** a tenant account owner submits a cancellation request with reason "price" and feedback "Competitor offers similar features at lower cost" **When** the POST endpoint is called **Then** a cancellation request record is created with `status=open`, the reason is categorized and logged, and an in-app notification is sent to the customer success team.
2. **Given** an open cancellation request **When** a CS agent proposes a retention offer with a 20% discount for 3 months **Then** the offer is stored in `retention_offers` with DECIMAL(10,2) values, an approval record is created in `audit_trail`, and the customer receives an email via Brevo with the offer details.
3. **Given** a retention offer exceeding $50/month in value **When** the CS agent submits the offer **Then** the BC-009 approval workflow is triggered, the offer is held in `pending_approval` status, and the supervisor sees the projected revenue impact in the Jarvis consequences display before approving or rejecting.
4. **Given** the cancellation analytics endpoint is called with `range=90d` **When** there are 50 cancellation requests in the period **Then** the response includes total requests, save rate percentage, top 3 reason categories with counts, average time to resolution, and retention offer effectiveness breakdown, all scoped to the requesting tenant's `company_id`.

---

# F-035: First Victory Celebration

## Overview
Celebratory modal and confetti animation triggered when the AI agent resolves its first customer ticket for a new tenant. This onboarding milestone feature uses canvas-based confetti, a personalized congratulatory message, and social sharing options to create a memorable "aha moment" that reinforces the value of PARWA and encourages continued platform adoption.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/onboarding/milestones/first-victory` | GET | `company_id` | `{ achieved: bool, achieved_at, ticket_id, ticket_summary }` |
| `/api/onboarding/milestones/first-victory/dismiss` | POST | `company_id` | `{ status: "dismissed" }` |
| `/api/onboarding/milestones/{company_id}/check` | POST | `company_id`, `event_type` (ticket_resolved) | `{ triggered: bool, milestone_type }` |
| *(Internal Socket.io event)* `milestone:first_victory` | — | `company_id`, `ticket_id` | Pushes celebration trigger to dashboard |

## DB Tables
- **`onboarding_milestones`** — `id`, `company_id`, `milestone_type` (first_ticket_created/first_victory/first_100_tickets/five_star_review/team_invited), `achieved` BOOL DEFAULT false, `achieved_at` TIMESTAMPTZ, `related_entity_id` UUID (e.g., ticket_id), `related_entity_type` VARCHAR(50), `dismissed` BOOL DEFAULT false, `dismissed_at` TIMESTAMPTZ, `celebration_data` (JSONB — confetti config, message template), `created_at`
  - **Indexes:** `UNIQUE(company_id, milestone_type)`, `idx_achieved` ON `(achieved, achieved_at)`
- **`onboarding_milestone_log`** — `id`, `company_id`, `milestone_type`, `event` (triggered/achieved/dismissed/shared), `event_data` (JSONB), `created_at`
  - **Indexes:** `idx_company_milestone` ON `(company_id, milestone_type)`

## BC Rules
- **BC-005** (Real-Time): First victory milestone is pushed in real-time via Socket.io to the `tenant_{company_id}` room. Event name: `milestone:first_victory`. If client is disconnected, the event is buffered in `event_buffer` and delivered on reconnection.
- **BC-006** (Email): An optional congratulatory email (template: `first_victory`) is sent to the account owner when the milestone is achieved. Email includes a summary of the resolved ticket and a CTA to explore analytics.
- **BC-001** (Multi-Tenant Isolation): Milestones scoped by `company_id`. No cross-tenant milestone comparison visible to users.
- **BC-012** (Error Handling): Confetti animation is a client-side enhancement. If the celebration modal fails to load (JS error), the AI ticket resolution still succeeds. Celebration is purely cosmetic — no data loss or functional impact on failure.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| AI resolves first ticket but human agent was also on the ticket | Milestone triggered only if `resolution_source = ai` in the ticket record. Human-resolved tickets do NOT trigger the celebration. |
| Multiple tickets resolved simultaneously (batch processing) | First ticket by timestamp triggers the milestone; subsequent tickets in the batch do NOT re-trigger. Check uses atomic `SELECT FOR UPDATE` on the milestone record. |
| User dismisses the celebration before the confetti finishes | Modal closes; confetti continues for 2 more seconds then fades (non-blocking). Dismissal state persisted so the modal doesn't reappear on page refresh. |
| Tenant achieves first victory but dashboard is not open | Socket.io event buffered in `event_buffer`; on next dashboard load or Socket.io reconnection, the milestone check endpoint returns `achieved=true` and the frontend renders the celebration. |
| Celebration triggers during a page transition/navigation | Celebration state stored in Redux/Zustand; if user navigates away, celebration resumes on next page load within the same session. |

## Acceptance Criteria
1. **Given** a new tenant whose AI agent has resolved zero tickets **When** the AI agent resolves its first ticket with `resolution_source=ai` **Then** the `onboarding_milestones` record for `first_victory` is set to `achieved=true`, and a Socket.io event `milestone:first_victory` is emitted to the tenant's room.
2. **Given** the Socket.io `milestone:first_victory` event is received by the dashboard frontend **When** the modal renders **Then** a full-screen celebration modal appears with canvas-based confetti animation (minimum 3 seconds), the resolved ticket summary, and a personalized congratulatory message referencing the tenant's industry.
3. **Given** the celebration modal is displayed **When** the user clicks "Share on LinkedIn" **Then** a pre-populated LinkedIn share dialog opens with a PARWA-branded message and the user can share without leaving the celebration experience.
4. **Given** a user dismisses the celebration modal **When** they refresh the dashboard **Then** the modal does NOT reappear, and the milestone is persisted as `dismissed=true` in the database with a `dismissed_at` timestamp.

---

# F-039: Adaptation Tracker (Day X/30)

## Overview
Visual progress indicator showing the AI agent's improvement over its 30-day adaptation period. The tracker displays daily resolution rates, confidence scores, accuracy trends, and customer satisfaction scores in a "Day X of 30" format, helping tenants understand that AI performance improves over time and setting realistic expectations during onboarding.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/adaptation/tracker` | GET | `company_id`, `agent_id` | `{ day: 1-30, start_date, metrics: { daily: [], cumulative: [] }, phase: (ramp_up/optimization/steady_state) }` |
| `/api/adaptation/tracker/history` | GET | `company_id`, `agent_id`, `granularity` (daily/weekly) | `{ data_points: [{ day, date, resolution_rate, confidence_avg, csat_avg, tickets_handled }] }` |
| `/api/adaptation/tracker/compare` | GET | `company_id`, `agent_id`, `compare_period` (week1/week2/week3/week4) | `{ period1: {}, period2: {}, improvement_pct }` |
| `/api/adaptation/benchmark` | GET | `company_id`, `industry_slug` | `{ industry_avg: { day7, day14, day30 }, your_agent: { day7, day14, day30 } }` |

## DB Tables
- **`adaptation_snapshots`** — `id`, `company_id`, `agent_id`, `snapshot_day` SMALLINT (1-30), `snapshot_date` DATE, `resolution_rate` DECIMAL(5,2), `confidence_avg` DECIMAL(5,2), `csat_avg` DECIMAL(3,2), `escalation_rate` DECIMAL(5,2), `avg_response_time_sec` INT, `tickets_handled` INT, `ai_resolved_tickets` INT, `mistakes_count` INT, `phase` (ramp_up/optimization/steady_state), `created_at`
  - **Indexes:** `UNIQUE(company_id, agent_id, snapshot_day)`, `idx_company_agent` ON `(company_id, agent_id)`, `idx_snapshot_date` ON `snapshot_date`
- **`adaptation_benchmarks`** — `id`, `industry_slug` VARCHAR(50), `metric_key` VARCHAR(50), `day_7` DECIMAL(5,2), `day_14` DECIMAL(5,2), `day_30` DECIMAL(5,2), `sample_size` INT, `updated_at`
  - **Indexes:** `UNIQUE(industry_slug, metric_key)`
- **`agent_activation`** — `id`, `company_id`, `agent_id`, `activated_at` TIMESTAMPTZ, `adaptation_complete` BOOL DEFAULT false, `adaptation_completed_at` TIMESTAMPTZ, `final_day_30_metrics` (JSONB)
  - **Indexes:** `UNIQUE(company_id, agent_id)`

## BC Rules
- **BC-001** (Multi-Tenant Isolation): All adaptation snapshots and benchmarks scoped by `company_id`. Industry benchmarks are aggregated from anonymized data and never expose individual tenant metrics.
- **BC-008** (State Management): Current adaptation day is derived from `agent_activation.activated_at` vs current date, stored in Redis (`parwa:{company_id}:agent:{agent_id}:adaptation_day`) as primary with PostgreSQL fallback.
- **BC-004** (Background Jobs): Daily snapshot computation runs as a Celery beat task (daily at 03:00 UTC) with `company_id` first param, `max_retries=3`. Computes resolution rate, confidence average, CSAT, and escalation rate for each active agent within its 30-day window.
- **BC-012** (Error Handling): If snapshot computation fails for a day, the previous day's data is used as fallback. Missing days are backfilled when the task succeeds on retry. The tracker UI shows a "data unavailable" indicator for missing days rather than incorrect data.
- **BC-007** (AI Model Interaction): Adaptation metrics feed into confidence threshold calibration (BC-007 rule 9). If day-30 metrics show confidence < 50%, system recommends additional training.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Agent is deactivated and reactivated (new 30-day period) | New `agent_activation` record created; `activated_at` reset to reactivation date; previous adaptation history preserved but marked as `previous_cycle`; tracker starts from Day 1 again |
| Tenant has zero tickets in the first 10 days | Adaptation tracker shows "Waiting for data" message; Day counter still advances; metrics display "N/A" for days with no data; benchmark comparison shows "insufficient data" |
| Agent completes 30-day adaptation with below-benchmark metrics | Tracker shows "Adaptation Complete" with a yellow warning indicator; system automatically recommends training (F-100) and displays the gap vs industry benchmark |
| Agent was trained mid-adaptation (F-100 triggered by 50 mistakes) | Adaptation tracker annotates the training event on the timeline; metrics before and after training are segmented; improvement post-training is highlighted |

## Acceptance Criteria
1. **Given** a newly activated AI agent on Day 5 of adaptation **When** the tracker endpoint is called **Then** the response returns `day: 5`, daily metrics for days 1-5, and the current `phase: "ramp_up"` with a visual progress bar at 16% (5/30).
2. **Given** daily snapshot computation runs at 03:00 UTC **When** a Celery task processes company ABC's agent **Then** a new `adaptation_snapshots` record is created with resolution_rate, confidence_avg, csat_avg, and escalation_rate calculated from the previous 24 hours of ticket data.
3. **Given** an agent reaches Day 30 **When** the snapshot task runs **Then** the `adaptation_complete` flag is set to `true`, `final_day_30_metrics` are stored in `agent_activation`, and a celebratory notification (similar to F-035 but smaller) is shown to the tenant.
4. **Given** the benchmark endpoint is called **When** the tenant belongs to the e-commerce industry **Then** the response includes industry average metrics for Day 7, 14, and 30 alongside the tenant's own agent metrics, with improvement percentage deltas displayed.

---

# F-051: Ticket Bulk Actions

## Overview
Multi-select toolbar enabling agents and supervisors to perform batch operations on tickets including status changes, reassignment, tagging, merging, exporting, and closing — all with confirmation dialogs and undo capability. This feature significantly improves operational efficiency for agents managing high-volume queues.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/tickets/bulk/status` | POST | `ticket_ids[]`, `new_status`, `reason` | `{ updated_count, failed: [], undo_token }` |
| `/api/tickets/bulk/assign` | POST | `ticket_ids[]`, `assignee_id` | `{ updated_count, failed: [], undo_token }` |
| `/api/tickets/bulk/tag` | POST | `ticket_ids[]`, `tags[]`, `action` (add/remove/set) | `{ updated_count, failed: [], undo_token }` |
| `/api/tickets/bulk/merge` | POST | `primary_ticket_id`, `ticket_ids[]` | `{ merged_ticket_id, merged_count, undo_token }` |
| `/api/tickets/bulk/close` | POST | `ticket_ids[]`, `close_reason`, `send_survey` (bool) | `{ closed_count, failed: [], undo_token }` |
| `/api/tickets/bulk/export` | POST | `ticket_ids[]`, `format` (csv/json), `columns[]` | `{ export_id, download_url, expires_at }` |
| `/api/tickets/bulk/undo` | POST | `undo_token` | `{ status: "undone", restored_count }` |
| `/api/tickets/bulk/validate` | POST | `ticket_ids[]`, `action` | `{ valid: bool, warning_count, warnings: [], estimated_time }` |

## DB Tables
- **`bulk_action_logs`** — `id`, `company_id`, `action_type` (status_change/reassign/tag/merge/close/export), `initiated_by` UUID, `ticket_ids` (JSONB — array), `action_details` (JSONB), `undo_token` UUID UNIQUE, `status` (pending/completed/partially_failed/failed/undone), `success_count` INT, `failure_count` INT, `completed_at` TIMESTAMPTZ, `undone_by` UUID, `undone_at` TIMESTAMPTZ, `undo_snapshot` (JSONB — pre-action state of all affected tickets), `created_at`
  - **Indexes:** `idx_company` ON `company_id`, `idx_initiator` ON `initiated_by`, `idx_undo_token` ON `undo_token`, `idx_created_at` ON `created_at`
- **`bulk_action_failures`** — `id`, `bulk_action_id` UUID REFERENCES `bulk_action_logs(id)`, `ticket_id` UUID, `failure_reason` TEXT, `created_at`
  - **Indexes:** `idx_bulk_action` ON `bulk_action_id`
- **`ticket_merges`** — `id`, `company_id`, `primary_ticket_id` UUID, `merged_ticket_ids` (JSONB — array), `merged_by` UUID, `created_at`
  - **Indexes:** `idx_primary` ON `primary_ticket_id`, `idx_company` ON `company_id`

## BC Rules
- **BC-009** (Approval Workflow): Bulk operations affecting > 50 tickets or involving `close` with `send_survey=true` require supervisor confirmation. Approval record created with action details and affected ticket count.
- **BC-001** (Multi-Tenant Isolation): All bulk operations scoped by `company_id`. Ticket IDs validated against the tenant before any modification. Cross-tenant ticket IDs in `ticket_ids[]` are silently filtered out and logged.
- **BC-004** (Background Jobs): Bulk operations on > 20 tickets run as a Celery task with `company_id` first param. Progress is tracked via `bulk_action_logs.status`. Real-time progress updates pushed via Socket.io.
- **BC-005** (Real-Time): Bulk operation progress (e.g., "Processing 45/100 tickets...") pushed via Socket.io to `tenant_{company_id}` room. Completed operations trigger a summary notification.
- **BC-012** (Error Handling): Partial failures are supported — successful operations commit, failed tickets are listed in `bulk_action_failures`. Undo is available for 24 hours via `undo_token`. Circuit breaker on bulk export if system is under heavy load.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Bulk merge of tickets from different customers | Validation rejects the merge with error "Cannot merge tickets from different customers." Frontend pre-validates via `/validate` endpoint before enabling merge button. |
| Bulk close with CSAT survey sends 200+ survey emails | Rate limiting applied (BC-006 rule 3: max 5 emails/customer/hour). Surveys are queued via Celery with throttling. If customer already received a survey in the last 7 days, skip. |
| Undo after 24-hour window | `undo_token` expires; endpoint returns 410 Gone with message "Undo window expired. Contact support for manual reversal." |
| Concurrent bulk operations on overlapping ticket sets | Second operation detects locked tickets (those currently being processed) and excludes them with a warning. No data corruption from concurrent modification. |
| Bulk export generates a file > 50MB | Export is processed as a Celery task; download URL is emailed to the initiator via Brevo (template: `export_ready`); URL expires after 24 hours; S3 presigned URL for download. |

## Acceptance Criteria
1. **Given** an agent selects 25 tickets and chooses "Close" with close reason "Resolved" **When** the bulk close endpoint is called **Then** all 25 tickets are updated to `status=closed`, a `bulk_action_log` is created with `undo_token`, and a confirmation notification is sent via Socket.io with the count.
2. **Given** a bulk action log with a valid `undo_token` **When** the undo endpoint is called within 24 hours **Then** all affected tickets are restored to their pre-action state using the `undo_snapshot`, the log status is updated to `undone`, and the user receives confirmation.
3. **Given** an agent selects 60 tickets for bulk reassignment **When** the bulk assign endpoint is called **Then** the BC-009 approval workflow is triggered (supervisor confirmation required for > 50 tickets), the operation is queued as a Celery task with `company_id` first param, and progress updates are pushed via Socket.io.
4. **Given** a bulk tag operation where 3 of 20 tickets fail validation **When** the operation completes **Then** 17 tickets are successfully tagged, 3 failures are logged in `bulk_action_failures` with specific reasons, and the response includes both `success_count=17` and `failed[]` array.

---

# F-063: Sentiment Analysis (Empathy Engine)

## Overview
Real-time sentiment detection engine that scores customer frustration from 0-100 on every incoming message, categorizes emotional tone (angry, sad, anxious, neutral, positive, confused), and uses these signals to drive AI tone adjustment, escalation triggers, and agent notifications. The Empathy Engine ensures PARWA's AI responds with appropriate emotional intelligence.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/sentiment/analyze` | POST | `message_text`, `ticket_id`, `language` (optional) | `{ score: 0-100, category, confidence, emotional_indicators: [], suggested_tone }` |
| `/api/sentiment/ticket/{ticket_id}` | GET | `ticket_id` | `{ timeline: [{ message_id, score, category, timestamp }], current_score, trend: "escalating/stable/de-escalating", escalation_triggered: bool }` |
| `/api/sentiment/thresholds` | GET | `company_id` | `{ escalation_threshold, tone_adjustment_thresholds: {} }` |
| `/api/sentiment/thresholds` | PUT | `company_id`, `escalation_threshold`, `tone_adjustment` (JSONB) | `{ updated: true }` |
| `/api/sentiment/analytics` | GET | `company_id`, `range`, `agent_id` (optional) | `{ avg_score, distribution: { angry: n, sad: n, ... }, escalation_rate, top_frustration_topics: [] }` |

## DB Tables
- **`sentiment_scores`** — `id`, `company_id`, `ticket_id`, `message_id`, `score` SMALLINT (0-100), `category` VARCHAR(20) (angry/sad/anxious/neutral/positive/confused), `confidence` DECIMAL(5,2), `emotional_indicators` (JSONB — e.g., `["exclamation_heavy", "all_caps", "negative_words"]`), `suggested_tone` VARCHAR(30), `model_used` VARCHAR(100), `processing_time_ms` INT, `created_at`
  - **Indexes:** `idx_ticket` ON `ticket_id`, `idx_company_score` ON `(company_id, score)`, `idx_category` ON `category`, `idx_created_at` ON `created_at`
- **`sentiment_thresholds`** — `id`, `company_id`, `escalation_threshold` SMALLINT DEFAULT 80, `angry_threshold` SMALLINT DEFAULT 70, `sad_threshold` SMALLINT DEFAULT 60, `anxious_threshold` SMALLINT DEFAULT 65, `positive_threshold` SMALLINT DEFAULT 30, `tone_adjustment` (JSONB — mapping of score ranges to tone directives), `updated_at`, `created_at`
  - **Indexes:** `UNIQUE(company_id)`
- **`sentiment_escalations`** — `id`, `company_id`, `ticket_id`, `trigger_score` SMALLINT, `trigger_category` VARCHAR(20), `escalated_to` UUID (agent/supervisor), `escalation_reason` TEXT, `action_taken` VARCHAR(50), `resolved` BOOL DEFAULT false, `created_at`
  - **Indexes:** `idx_ticket` ON `ticket_id`, `idx_company` ON `company_id`, `idx_resolved` ON `(resolved, created_at)`

## BC Rules
- **BC-007** (AI Model Interaction): Sentiment analysis uses Smart Router Light tier for efficiency. PII redaction applied before LLM call (BC-007 rule 5). Confidence threshold for auto-escalation stored per-company in `sentiment_thresholds` (BC-007 rule 9).
- **BC-007** Rule 6 (Guardrails): Sentiment scores are filtered through Guardrails to prevent bias, toxicity amplification, or misclassification of culturally specific expressions. Blocked classifications logged for review.
- **BC-004** (Background Jobs): Sentiment analysis runs as a Celery task immediately after message ingestion, with `company_id` first param, `max_retries=3`. Processing time tracked in `processing_time_ms`.
- **BC-005** (Real-Time): When sentiment score crosses the escalation threshold, a Socket.io event `sentiment:escalation` is pushed to `tenant_{company_id}` room with ticket details and sentiment timeline.
- **BC-001** (Multi-Tenant Isolation): All sentiment data scoped by `company_id`. No cross-tenant sentiment data sharing. Thresholds configurable per-tenant.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Customer uses sarcasm ("Oh great, another automated response") | Sentiment model trained on sarcasm detection patterns; emotional indicators include `["sarcasm_detected"]`; score reflects frustration (65-75) rather than positive; AI tone adjusted to empathetic |
| Message in a non-English language (French, Spanish, Arabic) | Language auto-detected via FastText lid; sentiment analysis prompt adapted to the detected language; score and category normalized to English categories for consistency |
| Rapid succession of messages with increasing frustration | Trend detection compares last 3 message scores; if delta > 15 per message, trend = "escalating"; escalation threshold lowered by 10 points for this ticket; supervisor notified proactively |
| Sentiment analysis model returns low confidence (< 40%) | Score still recorded but marked as `low_confidence`; AI response uses neutral tone as fallback; no auto-escalation triggered regardless of score; logged for model improvement (DSPy optimization) |
| Customer expresses frustration about a previous interaction (not current issue) | Context from ticket history is included in sentiment prompt; system distinguishes between frustration about current issue vs. systemic frustration; emotional indicators note `["contextual_frustration"]` |

## Acceptance Criteria
1. **Given** a customer sends a message with all-caps text and multiple exclamation marks ("THIS IS UNACCEPTABLE!!!") **When** the sentiment analysis processes the message **Then** a score of 80+ is returned with `category=angry`, emotional indicators include `["all_caps", "exclamation_heavy", "negative_words"]`, and the AI agent adjusts its tone to empathetic/apologetic.
2. **Given** a sentiment score crosses the company's escalation threshold (default 80) **When** the score is recorded **Then** a `sentiment_escalations` record is created, a Socket.io event is pushed to the tenant's room, and the ticket is flagged for priority review by a human agent.
3. **Given** a tenant with 1,000 analyzed messages over 30 days **When** the analytics endpoint is called **Then** the response includes average sentiment score, category distribution percentages, escalation rate, and top 5 frustration topics extracted from high-score messages.
4. **Given** a tenant customizes their escalation threshold to 70 **When** the PUT thresholds endpoint is called **Then** the threshold is updated in `sentiment_thresholds`, all future sentiment analyses for this tenant use the new threshold, and the change is logged in `audit_trail`.

---

# F-073: Temporary Agent Expiry & Deprovisioning

## Overview
Automated system that deprovisions temporary agents when their access period expires, revoking all permissions, reassigning any open tickets to active agents, and notifying the tenant of the change. This feature enforces BC-002 rule 11 (expiry_at timestamp on temp agents) and ensures no orphaned resources remain after agent access ends.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/agents/temp` | POST | `name`, `role`, `expiry_at`, `permissions[]` | `{ agent_id, status: "active", expires_at }` |
| `/api/agents/temp/{id}` | GET | `agent_id` | `{ agent, time_remaining, open_tickets, status }` |
| `/api/agents/temp/{id}/extend` | POST | `agent_id`, `new_expiry_at`, `justification` | `{ agent_id, new_expires_at, status: "extended" }` |
| `/api/agents/temp/{id}/convert` | POST | `agent_id` | `{ agent_id, status: "permanent", billing_update }` |
| `/api/agents/temp/expiring-soon` | GET | `company_id`, `days` (default 7) | `{ agents: [{ id, name, expires_at, open_tickets, days_remaining }] }` |
| *(Internal Celery beat task)* `deprovision_expired_agents` | — | Runs daily at 00:00 UTC | Checks and deprovisions expired temp agents |

## DB Tables
- **`agents`** — `id`, `company_id`, `name`, `type` (permanent/temporary), `status` (active/inactive/expired/deprovisioned), `role`, `permissions` (JSONB), `expiry_at` TIMESTAMPTZ (NULL for permanent), `deprovisioned_at` TIMESTAMPTZ, `deprovisioned_by` UUID, `reassignment_target_id` UUID, `created_at`, `updated_at`
  - **Indexes:** `idx_company_type` ON `(company_id, type)`, `idx_expiry` ON `(type, expiry_at)`, `idx_status` ON `status`
- **`agent_deprovision_log`** — `id`, `company_id`, `agent_id`, `deprovision_reason` (expired/manual/plan_downgrade), `open_tickets_at_deprovision` INT, `reassigned_tickets` INT, `failed_reassignments` INT, `permissions_revoked` (JSONB), `notifications_sent` INT, `duration_seconds` INT, `created_at`
  - **Indexes:** `idx_company` ON `company_id`, `idx_agent` ON `agent_id`, `idx_created_at` ON `created_at`
- **`ticket_reassignments`** — `id`, `company_id`, `ticket_id`, `from_agent_id` UUID, `to_agent_id` UUID, `reassignment_reason` (agent_expired/agent_deactivated/manual), `bulk_reassignment_id` UUID (nullable), `created_at`
  - **Indexes:** `idx_ticket` ON `ticket_id`, `idx_from_agent` ON `from_agent_id`, `idx_to_agent` ON `to_agent_id`

## BC Rules
- **BC-002** Rule 11: Every temporary agent MUST have an `expiry_at` timestamp. A Celery beat job checks daily for expired temporary agents and auto-deprovisions them. The deprovisioning process is atomic — all permissions revoked, all open tickets reassigned, or the entire operation rolls back.
- **BC-002** Rule 10: On plan downgrade, excess agents (including temp agents) MUST be scheduled for deprovisioning via Celery with appropriate delays. Temporary agents beyond the new plan limit are expired immediately.
- **BC-004** (Background Jobs): Deprovisioning runs as a Celery beat task (daily at 00:00 UTC) with `max_retries=3`, exponential backoff. Ticket reassignment is a sub-task with its own retry logic. DLQ for failed deprovisioning.
- **BC-001** (Multi-Tenant Isolation): All agent and ticket reassignment operations scoped by `company_id`. Temp agents can only be assigned to tickets within their own tenant.
- **BC-005** (Real-Time): Deprovisioning events pushed via Socket.io to `tenant_{company_id}` room. Notification includes agent name, reason, reassigned ticket count, and target agents.
- **BC-012** (Error Handling): If ticket reassignment fails for specific tickets, those tickets are flagged as `unassigned` (not lost). Failed reassignments logged in `agent_deprovision_log`. Ops team alerted if > 10% of reassignments fail.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Temp agent expires with 50+ open tickets | Reassignment is batch-processed via Celery with progress tracking; tickets distributed among active permanent agents using round-robin; supervisor notified if any agent receives > 10 reassigned tickets |
| Temp agent is the sole agent on the account | System warns before deprovisioning (7-day and 1-day advance notices); if no other agents exist at expiry, tickets are set to `unassigned` and account owner is urgently notified via email + in-app |
| Temp agent is in the middle of an active ticket conversation | Agent status set to `deprovisioned`; active conversation is NOT interrupted mid-message; any pending AI responses complete; subsequent messages are routed to reassigned agent |
| Admin extends temp agent expiry 1 day before expiration | Extension logged in `audit_trail`; `expiry_at` updated; no deprovisioning triggered; 7-day and 1-day warnings recalculated based on new expiry |
| Temp agent was created via integration API (e.g., Zendesk sync) | Deprovisioning also triggers an outbound API call to remove the agent from the integration; if API call fails, agent is still deprovisioned locally; sync discrepancy logged |

## Acceptance Criteria
1. **Given** a temporary agent with `expiry_at` set to yesterday **When** the daily deprovisioning Celery beat task runs **Then** the agent's status is updated to `deprovisioned`, all permissions are revoked, open tickets are reassigned to active permanent agents, and a `agent_deprovision_log` record is created with full details.
2. **Given** a temporary agent expiring in 7 days with 15 open tickets **When** the `/agents/temp/expiring-soon` endpoint is called with `days=7` **Then** the response includes the agent with `days_remaining=7`, `open_tickets=15`, and the account owner receives an email notification via Brevo warning about the upcoming expiry.
3. **Given** a deprovisioning operation where 3 of 20 ticket reassignments fail **When** the task completes **Then** 17 tickets are successfully reassigned, 3 tickets are flagged as `unassigned`, the `agent_deprovision_log` records `failed_reassignments=3`, and the ops team receives an alert if the failure rate exceeds 10%.
4. **Given** a tenant on a Growth plan with 5 permanent agents and 3 temp agents **When** they downgrade to Starter (max 3 agents) **Then** the 2 lowest-usage permanent agents and all 3 temp agents are queued for deprovisioning, with a 7-day grace period during which the tenant can upgrade or reassign tickets manually.

---

# F-114: Performance Comparison (Before/After)

## Overview
Analytics feature comparing AI agent performance metrics before and after significant events — training runs, prompt changes, configuration updates, knowledge base updates, or model provider switches. This enables data-driven evaluation of every change's impact on resolution rates, confidence scores, CSAT, and escalation rates.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/analytics/comparison` | POST | `company_id`, `agent_id`, `before` {from, to}, `after` {from, to}, `change_type` (training/prompt/config/kb/model) | `{ comparison: { metrics: {}, deltas: {}, significance: bool } }` |
| `/api/analytics/comparison/training/{run_id}` | GET | `training_run_id` | `{ before_metrics, after_metrics, delta, improvement_pct, recommendation }` |
| `/api/analytics/comparison/history` | GET | `company_id`, `agent_id`, `change_type` (optional) | `{ comparisons: [{ id, change_type, change_description, before_period, after_period, deltas }] }` |
| `/api/analytics/comparison/snapshot` | POST | `company_id`, `agent_id`, `label`, `change_description` | `{ snapshot_id, metrics_at_snapshot }` |
| `/api/analytics/comparison/export` | GET | `comparison_id`, `format` (csv/pdf) | `{ download_url }` |

## DB Tables
- **`performance_snapshots`** — `id`, `company_id`, `agent_id`, `label` VARCHAR(100), `change_type` (training/prompt/config/kb/model/manual), `change_description` TEXT, `related_entity_id` UUID (e.g., training_run_id), `resolution_rate` DECIMAL(5,2), `confidence_avg` DECIMAL(5,2), `csat_avg` DECIMAL(3,2), `escalation_rate` DECIMAL(5,2), `avg_response_time_sec` INT, `tickets_in_period` INT, `mistakes_in_period` INT, `qa_score_avg` DECIMAL(5,2), `snapshot_period_start` DATE, `snapshot_period_end` DATE, `created_by` UUID, `created_at`
  - **Indexes:** `idx_company_agent` ON `(company_id, agent_id)`, `idx_change_type` ON `change_type`, `idx_created_at` ON `created_at`, `idx_related_entity` ON `related_entity_id`
- **`performance_comparisons`** — `id`, `company_id`, `agent_id`, `before_snapshot_id` UUID, `after_snapshot_id` UUID, `change_type` VARCHAR(30), `change_description` TEXT, `delta_resolution_rate` DECIMAL(5,2), `delta_confidence_avg` DECIMAL(5,2), `delta_csat_avg` DECIMAL(3,2), `delta_escalation_rate` DECIMAL(5,2), `delta_avg_response_time_sec` INT, `improvement_overall` DECIMAL(5,2), `statistically_significant` BOOL, `recommendation` TEXT, `created_at`
  - **Indexes:** `idx_company_agent` ON `(company_id, agent_id)`, `idx_change_type` ON `change_type`, `idx_significance` ON `statistically_significant`

## BC Rules
- **BC-001** (Multi-Tenant Isolation): All performance snapshots and comparisons scoped by `company_id`. Agents can only compare metrics within their own tenant's data.
- **BC-004** (Background Jobs): Snapshot computation for large periods (> 30 days) runs as a Celery task with `company_id` first param, `max_retries=3`. Statistical significance calculation (t-test) runs client-side or in a separate task.
- **BC-007** (AI Model Interaction): Post-training comparisons are automatically triggered when a training run completes (F-100). Before-snapshot is taken at training start, after-snapshot at 7 days post-deployment (or configurable). Training run ID linked via `related_entity_id`.
- **BC-012** (Error Handling): If a comparison period has insufficient data (< 30 tickets), the system returns `statistically_significant=false` with a warning "Insufficient data for reliable comparison." No error is thrown.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Multiple changes occurred in the comparison period (training + prompt change) | System warns "Multiple changes detected in this period; isolate one change at a time for accurate comparison." User can manually create snapshots at specific points |
| Before period has no data (brand new agent) | Comparison shows after-period metrics only with label "Baseline not available. These are initial metrics." |
| Training run completed but agent hasn't handled any tickets yet (after period empty) | Comparison status set to `pending_data`; automatic retry scheduled for 24 hours later; snapshot taken once 30+ tickets are resolved post-training |
| Comparison shows negative delta (performance degraded after change) | Delta displayed in red with clear "Performance decreased" label; recommendation suggests reverting the change or initiating additional training; automated alert to account owner if degradation > 15% |

## Acceptance Criteria
1. **Given** a training run completed 7 days ago for agent X **When** the comparison endpoint is called with `change_type=training` and the training run ID **Then** the system returns before/after metrics for resolution rate, confidence, CSAT, and escalation rate, with delta values and an overall `improvement_overall` percentage.
2. **Given** a performance comparison with before-period CSAT of 3.8 and after-period CSAT of 4.2 **When** the response is rendered **Then** the delta of +0.4 is displayed with a green positive indicator, and `statistically_significant=true` is set if the p-value of the t-test is < 0.05.
3. **Given** an agent where a prompt change was deployed 14 days ago **When** the user creates a manual snapshot with label "Pre-prompt-change-v2" **Then** the current metrics are captured and stored in `performance_snapshots` with the label, change type, and related metadata for future comparison.
4. **Given** a comparison showing a 20% decrease in resolution rate after a configuration change **When** the comparison is saved **Then** `statistically_significant=true`, `recommendation` includes "Consider reverting configuration change", and an in-app alert is sent to the agent's supervisor via Socket.io.

---

# F-117: Analytics Data Export (CSV/PDF)

## Overview
Comprehensive data export feature allowing tenants to download all analytics data as CSV (for data analysis) or formatted PDF reports (for stakeholder sharing). Supports configurable date ranges, metric selections, and scheduled recurring exports. PDF reports include branded headers, charts, and executive summaries.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/analytics/export` | POST | `format` (csv/pdf), `metrics[]`, `date_from`, `date_to`, `agents[]` (optional), `channels[]` (optional), `include_charts` (bool, PDF only) | `{ export_id, status: "processing", estimated_time }` |
| `/api/analytics/export/{id}` | GET | `export_id` | `{ export_id, status, download_url, expires_at, file_size }` |
| `/api/analytics/export/{id}/cancel` | POST | `export_id` | `{ status: "cancelled" }` |
| `/api/analytics/export/scheduled` | POST | `schedule` (weekly/monthly), `format`, `metrics[]`, `recipients[]` | `{ schedule_id, next_run_at }` |
| `/api/analytics/export/scheduled/{id}` | PUT | `schedule_id`, `updates` | `{ schedule_id, status: "updated" }` |
| `/api/analytics/export/scheduled/{id}` | DELETE | `schedule_id` | `{ status: "deleted" }` |
| `/api/analytics/export/history` | GET | `company_id`, `status` (all/completed/failed/expired) | `{ exports: [{ id, format, metrics, date_range, status, created_at }] }` |

## DB Tables
- **`analytics_exports`** — `id`, `company_id`, `format` (csv/pdf), `metrics` (JSONB — selected metrics), `date_from` DATE, `date_to` DATE, `agent_ids` (JSONB), `channel_filters` (JSONB), `include_charts` BOOL DEFAULT false, `status` (pending/processing/completed/failed/cancelled/expired), `file_s3_key` TEXT, `file_size_bytes` INT, `download_url` TEXT, `expires_at` TIMESTAMPTZ, `celery_task_id` VARCHAR(255), `error_message` TEXT, `initiated_by` UUID, `created_at`, `completed_at`
  - **Indexes:** `idx_company` ON `company_id`, `idx_status` ON `status`, `idx_created_at` ON `created_at`, `idx_expires` ON `expires_at`
- **`scheduled_exports`** — `id`, `company_id`, `schedule_type` (weekly/monthly), `format` (csv/pdf), `metrics` (JSONB), `agent_ids` (JSONB), `channel_filters` (JSONB), `recipients` (JSONB — array of emails), `include_charts` BOOL, `last_run_at` TIMESTAMPTZ, `next_run_at` TIMESTAMPTZ, `active` BOOL DEFAULT true, `created_by` UUID, `created_at`, `updated_at`
  - **Indexes:** `idx_company_active` ON `(company_id, active)`, `idx_next_run` ON `next_run_at`
- **`analytics_export_logs`** — `id`, `export_id` UUID, `company_id`, `event` (created/started/completed/failed/downloaded/expired), `event_data` (JSONB), `created_at`
  - **Indexes:** `idx_export` ON `export_id`, `idx_company` ON `company_id`

## BC Rules
- **BC-001** (Multi-Tenant Isolation): All export data scoped by `company_id`. Exports can only include data from the requesting tenant. Agent IDs and channel filters validated against tenant scope before query execution.
- **BC-004** (Background Jobs): Export generation runs as a Celery task with `company_id` first param, `max_retries=3`, `soft_time_limit=300` (5 minutes). Large exports (> 100K rows) use streaming CSV generation to avoid memory issues. PDF generation uses headless Chrome via Playwright.
- **BC-006** (Email): Scheduled exports are delivered via Brevo email (template: `analytics_report`) to the configured recipients. Download link included with expiration timestamp. BC-006 rule 3 rate limiting applied per recipient.
- **BC-010** (Data Lifecycle): Export files stored in S3 with 7-day TTL. After expiry, files are automatically deleted by a Celery beat task. PII in exports is redacted per BC-007 rule 5.
- **BC-012** (Error Handling): Export failures (PDF rendering crash, S3 upload failure, query timeout) are caught, logged, and retried. User is notified of failure via in-app notification. Circuit breaker disables export for tenants with > 3 consecutive failures until ops review.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Export date range spans > 2 years | System warns "Large date range may take several minutes." Export runs as Celery task with extended timeout (soft_time_limit=600). Progress updates pushed via Socket.io. |
| CSV export exceeds 10MB | File is compressed to ZIP format; download URL points to the ZIP file. Header row included with column descriptions. Large files streamed directly to S3 without loading into memory. |
| PDF generation fails (Chrome crash, memory limit) | Retry up to 3 times; if still failing, fall back to CSV-only format with message "PDF generation unavailable. CSV export has been generated instead." |
| Tenant exports data containing customer PII | All customer names, emails, and phone numbers are redacted in the export (BC-007 rule 5). Redaction applied during query, not as post-processing. |
| Scheduled export recipient is no longer a valid team member | Email still sent (may bounce); next run, system checks recipient validity and deactivates invalid recipients with a log entry. Admin notified of deactivated scheduled export. |

## Acceptance Criteria
1. **Given** a tenant selects metrics [resolution_rate, csat_avg, escalation_rate] for date range 2025-01-01 to 2025-01-31 in PDF format **When** the export endpoint is called **Then** a Celery task is queued, and upon completion, a branded PDF report is generated with metric tables, trend charts, and an executive summary, stored in S3 with a presigned download URL.
2. **Given** an export is requested in CSV format with 50,000 data rows **When** the export task runs **Then** the CSV is generated using streaming (chunked processing), uploaded to S3, and the response includes a download URL that expires in 7 days with the correct `file_size_bytes`.
3. **Given** a scheduled weekly export configured for every Monday at 08:00 UTC **When** the Celery beat task triggers **Then** the export is generated, uploaded to S3, and a Brevo email (template: `analytics_report`) is sent to all configured recipients with the download link and expiration date.
4. **Given** an export task fails after 3 retries **When** the Celery task routes to the DLQ **Then** the export status is set to `failed` with an `error_message`, an in-app notification is sent to the initiating user, and the ops team receives an alert with the export ID and failure details.

---

# F-122: OOO/Auto-Reply Detection

## Overview
Email processing filter that detects out-of-office (OOO) and auto-reply messages from customer emails using header analysis, content pattern matching, and sender behavior heuristics. Detected messages are tagged, excluded from AI processing, and prevented from creating unnecessary tickets or triggering responses — implementing BC-006 rule 1 and preventing email loops.

## APIs
| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|----------|
| `/api/email/ooo/check` | POST | `email_headers` (JSONB), `body_text` | `{ is_auto_reply: bool, type: (ooo/auto_reply/cyclic/spam), confidence, detected_signals: [] }` |
| `/api/email/ooo/rules` | GET | `company_id` | `{ custom_rules: [{ pattern, type, active }], global_rules_count }` |
| `/api/email/ooo/rules` | POST | `company_id`, `pattern`, `type`, `active` | `{ rule_id, status: "created" }` |
| `/api/email/ooo/rules/{id}` | PUT | `rule_id`, `updates` | `{ rule_id, status: "updated" }` |
| `/api/email/ooo/rules/{id}` | DELETE | `rule_id` | `{ status: "deleted" }` |
| `/api/email/ooo/stats` | GET | `company_id`, `range` (7d/30d/90d) | `{ detected_count, by_type: {}, top_senders: [], loop_prevented_count }` |
| *(Internal — called before ticket creation)* `detect_auto_reply` | — | `company_id`, `email_data` | Returns `is_auto_reply` flag; if true, email is tagged and not processed as a ticket |

## DB Tables
- **`ooo_detection_rules`** — `id`, `company_id` (NULL for global rules), `rule_type` (header/body/sender_behavior/frequency), `pattern` TEXT, `pattern_type` (regex/substring/contains), `classification` (ooo/auto_reply/cyclic/spam), `active` BOOL DEFAULT true, `match_count` INT DEFAULT 0, `last_matched_at` TIMESTAMPTZ, `created_at`, `updated_at`
  - **Indexes:** `idx_company_active` ON `(company_id, active)`, `idx_classification` ON `classification`
- **`ooo_detection_log`** — `id`, `company_id`, `thread_id` UUID, `sender_email` VARCHAR(255), `classification` (ooo/auto_reply/cyclic/spam), `confidence` DECIMAL(5,2), `detected_signals` (JSONB — e.g., `["header:auto_submitted", "body:ooo_keywords"]`), `rule_ids_matched` (JSONB), `action_taken` (tagged/suppressed/loop_prevented), `related_ticket_id` UUID, `message_id` VARCHAR(255), `created_at`
  - **Indexes:** `idx_company` ON `company_id`, `idx_sender` ON `sender_email`, `idx_classification` ON `classification`, `idx_created_at` ON `created_at`
- **`ooo_sender_profiles`** — `id`, `company_id`, `sender_email` VARCHAR(255), `ooo_detected_count` INT DEFAULT 0, `last_ooo_at` TIMESTAMPTZ, `ooo_until` TIMESTAMPTZ (extracted from OOO body — return date), `active_ooo` BOOL DEFAULT false, `created_at`, `updated_at`
  - **Indexes:** `UNIQUE(company_id, sender_email)`, `idx_active_ooo` ON `(company_id, active_ooo)`

## BC Rules
- **BC-006** Rule 1: Before processing any inbound email, the system MUST check for auto-reply headers (`X-Auto-Response-Suppress`, `Auto-Submitted`, `X-Auto-Reply`). If present, the email is tagged as auto-reply and NOT processed as a ticket. This is the primary email loop prevention mechanism.
- **BC-006** Rule 2: OOO detection is a complementary layer to the 5-replies/thread/24h rate limit. Even if OOO detection fails, the rate limit prevents infinite loops. Together, they provide defense in depth.
- **BC-001** (Multi-Tenant Isolation): OOO detection rules and logs scoped by `company_id`. Global rules (company_id=NULL) are available to all tenants but can be overridden by tenant-specific rules.
- **BC-004** (Background Jobs): OOO sender profile cleanup runs as a Celery beat task (daily) — resets `active_ooo=false` for profiles where `ooo_until` has passed.
- **BC-012** (Error Handling): If OOO detection fails (regex error, missing headers), the email is still processed normally. OOO detection is a safety filter — failure should never block legitimate email processing. Errors logged for pattern improvement.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| OOO message includes a return date ("I'll be back on Jan 15") | Natural language date extraction parses the return date; `ooo_sender_profiles.ooo_until` is set to the extracted date; system auto-resumes normal processing after the date passes |
| Customer sends OOO in a non-English language ("Fuera de la oficina") | Multi-language keyword matching applied (OOO keywords in 15+ languages); body pattern detection supplemented by header-based detection which is language-independent |
| Auto-reply is a cyclic message (e.g., "Your ticket has been received") | Frequency analysis detects if the same sender sends identical/similar messages within a short window; `classification=cyclic`; sender flagged in `ooo_sender_profiles` to prevent ticket creation from this sender |
| Legitimate customer email has OOO-like words in the body ("I was out of office when this happened") | Confidence scoring considers full context — header signals weighted higher than body signals. Body-only detection below 70% confidence does NOT classify as OOO. Human review queue for borderline cases. |
| Customer's email server sends a delivery status notification (DSN) | DSN messages detected via `Content-Type: multipart/report` header; classified as `auto_reply`; not processed as tickets; logged for deliverability monitoring |

## Acceptance Criteria
1. **Given** an inbound email with `Auto-Submitted: auto-replied` header **When** the OOO detection check runs **Then** the email is classified as `auto_reply` with `confidence=100`, logged in `ooo_detection_log`, and the ticket creation pipeline is bypassed entirely.
2. **Given** an inbound email without auto-reply headers but with body text containing "I am out of the office until December 25" **When** the OOO detection check runs **Then** the email is classified as `ooo` with body-based pattern matching, the `ooo_sender_profiles` record is updated with `ooo_until=2025-12-25`, and `active_ooo=true`.
3. **Given** a sender with `active_ooo=true` and `ooo_until` in the past **When** the daily cleanup Celery beat task runs **Then** the sender's `active_ooo` flag is set to `false`, and future emails from this sender are processed normally without OOO filtering.
4. **Given** a tenant creates a custom OOO detection rule with pattern "Cerrado por vacaciones" (Spanish) **When** an inbound email matches this pattern **Then** the custom rule is matched, `match_count` is incremented, and the email is classified according to the rule's `classification` type, with the matched rule ID logged in the detection log.
