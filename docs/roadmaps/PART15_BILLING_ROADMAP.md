# Part 15: Billing & Revenue — Complete Build Plan

> **Status:** Deep Audit Complete — Ready to Build
> **Priority:** P0 — Revenue engine. Clients pay $999-$3,999/month. Must be bulletproof.
> **Current:** ~50% complete (core flows exist, but 5 critical architectural bugs + 33 gaps)
> **Dependencies:** Part 12 (Dashboard billing UI) for frontend. Backend can be built independently.
> **Created:** April 16, 2026
> **Audit:** Deep code audit of 15 billing files. Found 43 issues (5 critical, 5 high, 17 medium, 6 low).

---

## AUDIT SUMMARY — THE REAL STATE

### What Works:
- Monthly subscription creation via Paddle
- Mid-month upgrades with proration
- Cancel with Netflix-style grace period (access until period end)
- Reactivation during grace period
- Overage calculation ($0.10/ticket, daily cron)
- Invoice sync and PDF download
- Usage tracking model (but NOT hooked to ticket lifecycle)
- Webhook processing (18 endpoints, 25+ event handlers)
- Proration calculation (Decimal math, audit trail)

### What's Broken (Critical):
1. **Downgrades scheduled but NEVER executed** — no cron job applies pending downgrades at period end
2. **Usage metering NOT hooked to ticket lifecycle** — `tickets_used` never auto-incremented, overage charges are always $0
3. **Industry variants DISCONNECTED from billing** — variant purchases are cosmetic, never affect entitlements or limits
4. **Entitlement enforcement only works for tickets** — agents, team, KB docs, voice channels have NO limits enforced
5. **Calendar month vs billing period misalignment** — usage resets on 1st, billing resets on subscription anniversary

### Bugs Found (10):
| # | Bug | Severity |
|---|-----|----------|
| 1 | Email says "48 hours" but code does immediate stop | High |
| 2 | `create_transaction()` not defined on PaddleClient — overage crashes | Critical |
| 3 | Double-counting tickets in month-to-date calculation | Critical |
| 4 | AI agents NOT actually stopped on payment failure (`agents_stopped=0`) | High |
| 5 | Ticket status lost on resume (all become "open") | Medium |
| 6 | Unknown variant IDs get fake price IDs — Paddle fails silently | Medium |
| 7 | ReAct billing tool uses wrong plan names | Low |
| 8 | Two different HMAC verification implementations | Low |
| 9 | In-memory idempotency lost on restart | Medium |
| 10 | Paddle reconciliation uses `shared_task` vs `app.task` — different Celery apps | Low |

### Missing Features (33 gaps):
- Yearly billing cycle
- Exact 30-day billing periods
- Variant add-on management (add/remove)
- Mid-year variant purchase with proration
- Resource cleanup on downgrade (agents, team, docs, voice)
- Refund system for subscriptions
- Chargeback handling
- Voice/SMS/email usage metering
- Customer-configurable spending cap
- Webhook backfill mechanism
- Data export before cancel
- Data retention policy after cancel
- Re-subscription flow
- Corporate/B2B invoicing
- Trial period
- Discount/promo codes
- Subscription pause/resume
- Invoice amendments
- Credit balance system
- Multi-currency support
- Company timezone for billing
- Spending analytics per channel
- Budget alerts ($ amount)
- Middleware fail-closed (currently fail-open)
- Payment method update endpoint
- Period-end automation cron
- Variant knowledge cleanup on removal
- Reactivation after grace period
- Billing period edge month handling
- Spending cap hard stop
- Overlimit soft/hard limit for ALL resources

---

## PRICING MODEL (Current)

### Subscription Tiers:

| Tier | Code | Tickets/Mo | AI Agents | Team | Voice Ch | KB Docs | Price/Mo | Price/Yr |
|------|------|-----------|-----------|------|----------|---------|----------|----------|
| Mini PARWA | `starter` | 2,000 | 1 | 3 | 0 | 100 | $999 | $9,990 (2 mo free) |
| PARWA | `growth` | 5,000 | 3 | 10 | 2 | 500 | $2,499 | $24,990 (2 mo free) |
| PARWA High | `high` | 15,000 | 5 | 25 | 5 | 2,000 | $3,999 | $39,990 (2 mo free) |

### Industry Variant Add-ons:

| Variant | Price/Mo | Tickets Added | Features |
|---------|----------|---------------|----------|
| E-commerce | $79 | +500 | Order tracking, refund handling, product FAQ |
| SaaS | $59 | +300 | Technical support, bug triage, feature requests |
| Logistics | $69 | +400 | Shipment tracking, delivery updates, returns |
| Others | $39 | +200 | General support, FAQ, escalation |

### Overage Rate: $0.10/ticket over plan limit

---

## USER SCENARIOS TO COVER

### Scenario 1: Yearly Subscriber Buys Variant Mid-Year
- Customer pays annually for PARWA ($24,990)
- 6 months in, they want to add E-commerce variant ($79/mo)
- Must prorate: $79 x 6 remaining months / 12 = $39.50 charge
- Variant activates immediately with 500 extra tickets
- At renewal, variant auto-renews at $79/mo
- Customer can remove variant at renewal time

### Scenario 2: 30-Day Billing Period (Always Exactly 30 Days)
- Not calendar months (28/29/30/31 days varying)
- Period starts on subscription date, adds exactly 30 days
- Jan 15 → Feb 14 (30 days), Feb 14 → Mar 16 (30 days)
- Usage resets on billing period start, not calendar month start
- Overage calculated per billing period, not calendar month

### Scenario 3: Netflix-Style Cancel (Already Paid = Full Access)
- Customer cancels: service continues until period end
- If auto-pay is removed: still runs for paid period (30 days from last charge)
- At period end: service stops, data preserved for 30 days
- Data export available during grace period
- Can reactivate within 30 days and get data back
- After 30 days: data archived/deleted per retention policy

### Scenario 4: Quota Finished But Days Left (Daily Overage)
- Customer hits 2,000 ticket limit on Day 18 of 30-day period
- System warns at 80% (1,600 tickets) — soft limit alert
- At 100% — hard stop option OR overage kicks in
- Customer chooses: Block new tickets (hard cap) OR Continue at $0.10/ticket (overage)
- Daily overage charges processed each night
- Customer can self-set a spending cap: "Max $50/mo in overage, then block"

### Scenario 5: Subscriber Adds/Removes Variants
- Add variant: immediate activation, prorated charge for remaining period
- Remove variant: takes effect at next period end (not mid-period)
- Variant knowledge/training data archived (not deleted) on removal
- Can re-add same variant later and get archived data back

### Scenario 6: Downgrade with Resource Cleanup
- Downgrade from PARWA (3 agents, 10 team, 2 voice, 500 docs) to Mini (1 agent, 3 team, 0 voice, 100 docs)
- Takes effect at period end (not immediately)
- At period end cron:
  - Pause extra agents (2 agents paused, not deleted)
  - Disable extra team member logins (7 members downgraded to read-only)
  - Archive extra KB docs beyond 100 (not deleted, just inaccessible)
  - End voice channel access
  - Customer warned 7 days before change takes effect

### Scenario 7: Payment Failure Handling
- Payment fails: service stops IMMEDIATELY (no 48-hour grace — fix email)
- Customer notified via email + Socket.io + dashboard alert
- Can update payment method and resume immediately
- If not fixed within 7 days: subscription canceled, 30-day data retention starts
- Chargebacks: webhook handler, service stopped, flagged for review

### Scenario 8: Upgrade Mid-Period
- Upgrade from Mini to PARWA mid-month
- Proration: credit for unused Mini days + charge for PARWA remaining days
- Extra agent slots, team slots, etc. available IMMEDIATELY
- Paddle subscription updated, invoice generated

---

## 6-DAY BUILD PLAN

### DAY 1 — Fix Critical Bugs + Usage Metering + Entitlement Enforcement
**Goal:** Fix the 5 things that are fundamentally broken. Make billing actually work.

#### Bug Fixes (Critical):

| ID | Bug | Fix |
|----|-----|-----|
| B1 | `create_transaction()` not on PaddleClient | Add the method to `paddle_client.py`. Use Paddle's Transactions API: `POST /transactions` with `items`, `customer_id`, `currency`. Handle response and return transaction ID |
| B2 | Double-counting in overage month-to-date | Fix `get_month_to_date_usage()` in `overage_service.py`. Use proper aggregation query instead of summing all records including target date's separate record |
| B3 | Email says 48 hours but code stops immediately | Fix `payment_failure_service.py:203`. Change email copy to: "Your AI agents have been stopped immediately. Please update your payment method to resume service." Add second email template for 7-day final warning |
| B4 | AI agents not stopped on payment failure | Fix `stop_service_immediately` in `payment_failure_tasks.py`. Replace `agents_stopped = 0` with actual call to agent service to pause all active agents for the company. Track count in response |
| B5 | Ticket status lost on resume | Fix `resume_service` in `payment_failure_tasks.py`. Store original ticket status in a `frozen_ticket_statuses` map before freezing. On resume, restore each ticket to its original status instead of forcing "open" |
| B6 | HMAC inconsistency | Standardize to ONE implementation. Keep `PaddleClient.verify_webhook_signature()` (the more robust one with timestamp replay protection). Remove duplicate from `billing_webhooks.py` |
| B7 | ReAct billing tool wrong plan names | Update `billing_tool.py` to use actual tier names: `starter`/`growth`/`high` and map to marketing names: Mini PARWA/PARWA/PARWA High |
| B8 | In-memory idempotency | Move to Redis with 48h TTL. `is_duplicate_event()` and `mark_event_processed()` use `redis.setex(key, 172800, "1")`. Fallback to DB `IdempotencyKey` table if Redis unavailable |

#### Usage Metering (Hook into Ticket Lifecycle):

| ID | Item | Details |
|----|------|---------|
| M1 | Hook ticket creation to usage | In ticket service, after ticket is created: call `overage_service.record_ticket_usage(company_id, count=1, target_date=today)`. This auto-increments `tickets_used` |
| M2 | Hook ticket resolution to usage | Same hook at resolution time. Track both created and resolved counts separately |
| M3 | Fix billing period alignment | Change usage queries from calendar month (`strftime("%Y-%m")`) to billing period (`period_start <= date <= period_end`). Create helper `get_current_billing_period(company_id)` that returns start/end based on subscription |
| M4 | Usage reset at billing period start | When new billing period starts (period_end passes), create new `UsageRecord` with `tickets_used=0`. Previous period's records stay for history |
| M5 | Fix overage price ID | Replace hardcoded `pri_overage` with proper Paddle price ID from env var `PADDLE_OVERAGE_PRICE_ID`. Add validation that price ID exists before charging |

#### Entitlement Enforcement (Fix Middleware):

| ID | Item | Details |
|----|------|---------|
| E1 | Fix VariantCheckMiddleware | Change fail-open to **fail-closed**. If limit check throws error, BLOCK the request (return 402). Only allow on explicit success |
| E2 | Wire all resource checks | Make middleware actually call enforcement for ALL resources, not just tickets: agents (`check_ai_agent_limit()`), team (`check_team_member_limit()`), KB (`check_kb_doc_limit()`), voice (`check_voice_slot_limit()`) |
| E3 | Add enforcement to service layer | Don't rely only on middleware. Add limit checks directly in: agent creation service, team invite service, KB upload service, voice provisioning service |
| E4 | Read limits from DB, not hardcoded | `VARIANT_LIMITS` is hardcoded in schemas. Move to `VariantLimit` DB table (already exists in `billing_extended.py`). Service reads from DB per company's current tier + active variants |
| E5 | Add variant ticket stacking | When industry variants are purchased, their ticket allocations ADD to the base plan total. `effective_ticket_limit = base_plan_limit + sum(variant_ticket_additions)` |

**Day 1 Deliverables:**
- All 8 critical bugs fixed
- Usage metering hooked to ticket lifecycle
- Billing period alignment fixed
- Entitlement enforcement working for ALL resources (agents, team, KB, voice, tickets)
- Variant ticket allocations connected to billing
- Fail-closed middleware

**Day 1 Total: 18 items**

---

### DAY 2 — Downgrade Execution + Yearly Billing + 30-Day Periods
**Goal:** Fix the core billing cycle engine. Make downgrades, yearly, and 30-day periods work.

#### Downgrade Execution (Period-End Cron):

| ID | Item | Details |
|----|------|---------|
| D1 | Period-end automation cron | New Celery task: `process_period_end_transitions()`. Runs daily at midnight UTC. Queries all subscriptions where: `cancel_at_period_end=True AND period_end <= today` OR `pending_downgrade_variant IS NOT NULL AND period_end <= today` |
| D2 | Apply pending downgrade | For subscriptions with pending downgrade: update `subscription.tier` to pending variant, update `company.subscription_tier`, clear `pending_downgrade_variant`, set new period dates, sync to Paddle |
| D3 | Apply scheduled cancellation | For subscriptions with `cancel_at_period_end=True` and period ended: set `status='canceled'`, trigger 30-day data retention timer |
| D4 | Resource cleanup on downgrade | After tier change: (a) Pause extra AI agents — set `status='paused'` for agents beyond new limit, (b) Downgrade extra team members — set `role='viewer'` or `is_active=False` for members beyond new limit, (c) Archive extra KB docs — set `is_archived=True` for docs beyond new limit (not deleted), (d) Disable voice channels — stop accepting voice calls on removed channels |
| D5 | Pre-downgrade warning | 7 days before period end with pending downgrade: send email + notification warning about what resources will be affected. "In 7 days, 2 agents will be paused, 7 team members will lose access, 400 documents will be archived." |
| D6 | Downgrade undo window | Within 24 hours of downgrade execution: allow customer to undo. Restore previous tier, unpause agents, restore team roles, unarchive docs. After 24 hours: permanent |

#### Yearly Billing:

| ID | Item | Details |
|----|------|---------|
| Y1 | Add billing_frequency to Subscription model | New column: `billing_frequency` enum: `monthly`, `yearly`. Default: `monthly` |
| Y2 | Yearly pricing in Paddle | Create yearly price IDs in Paddle for each tier: starter=$9,990/yr, growth=$24,990/yr, high=$39,990/yr. Store in `PADDLE_YEARLY_PRICE_IDS` env var |
| Y3 | Yearly subscription creation | Update `create_subscription()` to accept `billing_frequency` parameter. Create Paddle subscription with yearly price ID |
| Y4 | Yearly period calculation | `_calculate_period_end()`: if yearly, add 365 days (or 366 for leap year). If monthly, add 30 days (see below) |
| Y5 | Upgrade/downgrade with yearly | If customer is yearly and upgrades mid-year: proration covers remaining months. New tier applied with yearly frequency. Credit: `(annual_price_old / 365) * days_remaining`. Charge: `(annual_price_new / 365) * days_remaining` |
| Y6 | Yearly renewal handling | At period end for yearly subscriptions: auto-renew via Paddle. Send renewal reminder 30 days before |
| Y7 | Switch frequency | Allow customer to switch from monthly to yearly (prorate remaining months) or yearly to monthly (credit remaining annual value). Not a tier change — same tier, different frequency |

#### Exact 30-Day Billing Periods:

| ID | Item | Details |
|----|------|---------|
| P1 | Replace `relativedelta(months=+1)` | In `_calculate_period_end()`: use `timedelta(days=30)` ALWAYS. Not `relativedelta` which gives variable days per month |
| P2 | Update all period calculations | Search all code for `relativedelta` in billing context and replace with `timedelta(days=30)`. Ensure consistency |
| P3 | Proration uses 30-day divisor | In `proration_service.py`: `daily_rate = price / 30` (not `days_in_period` which varies). All plans are 30-day periods |
| P4 | Usage period aligned to billing period | Usage records use billing period start/end, not calendar month. `get_current_billing_period()` returns the 30-day window |
| P5 | Leap year handling | For yearly plans: check if period includes Feb 29 and add 366 days. Store `days_in_period` on subscription record for audit |

**Day 2 Deliverables:**
- Downgrade cron working (executes at period end)
- Resource cleanup on downgrade (agents paused, team downgraded, docs archived, voice disabled)
- Pre-downgrade 7-day warning
- Yearly billing cycle working
- Monthly-to-yearly and yearly-to-monthly switching
- Exact 30-day billing periods everywhere
- Usage aligned to billing periods (not calendar months)

**Day 2 Total: 18 items**

---

### DAY 3 — Variant Add-On Management + Mid-Year Variant Purchase
**Goal:** Let customers add/remove industry variants at any time. Properly connected to billing.

#### Variant Add-On System:

| ID | Item | Details |
|----|------|---------|
| V1 | Active variant tracking model | New DB model: `CompanyVariant` — company_id, variant_id, status (active/inactive/archived), activated_at, deactivated_at, paddle_subscription_item_id, price_per_month |
| V2 | Add variant API | `POST /api/billing/variants` — accept variant_id, billing_frequency (inherit from subscription or monthly). Create Paddle subscription item (add-on to existing subscription). Create `CompanyVariant` record. Add variant's ticket allocation to effective limit |
| V3 | Remove variant API | `DELETE /api/billing/variants/{variant_id}` — if within current period: deactivate at period end (don't prorate refund for partial period). Set `status='inactive'`, set `deactivated_at=period_end`. At period end cron: remove Paddle subscription item, archive variant knowledge |
| V4 | Variant list API | `GET /api/billing/variants` — list all active/inactive variants for company. Show: variant name, price, status, activation date, next billing date |
| V5 | Mid-year variant proration | Yearly customer adds variant mid-year: charge = `(variant_annual_price / 365) * days_remaining_in_period`. For monthly: charge = `(variant_monthly_price / 30) * days_remaining`. Create proration audit record |
| V6 | Variant entitlement stacking | When variant is active: `effective_tickets = base_plan_tickets + sum(active_variant_tickets)`. Recalculate on: variant add, variant remove, plan change, period start |
| V7 | Variant removal at period end | Extend period-end cron: check for variants with `deactivated_at <= today`. Remove from Paddle subscription. Archive variant-specific KB data (not delete). Reduce effective ticket limit. Send notification |
| V8 | Variant knowledge archive | On variant removal: move variant-specific KB documents to `archived=True`. Move variant-specific training data to cold storage. If customer re-adds same variant: restore from archive instead of fresh start |
| V9 | Variant in dashboard UI | (Part 12 dependency) Variant management section in Billing page: list active variants, add/remove buttons, cost breakdown |
| V10 | Variant cost in invoices | Paddle generates invoices with line items: base plan + each variant. Local invoice sync picks up all line items |

#### Variant + Base Plan Interaction Rules:

| Rule | Description |
|------|-------------|
| Tickets Stack | Base plan tickets + all active variant tickets = total ticket limit |
| Agents Don't Stack | Variant purchase doesn't add agent slots. Agent count comes from base plan only |
| Team Don't Stack | Same — team limits from base plan only |
| KB Docs Stack | Variant KB docs ADD to base plan docs. E.g., Mini (100) + E-commerce (50) = 150 docs |
| Voice Doesn't Stack | Voice slots from base plan only |
| Min Base Plan | Can't go below Mini PARWA even with all variants |

**Day 3 Deliverables:**
- Variant add/remove API endpoints
- CompanyVariant DB model
- Mid-year variant purchase with proration
- Variant entitlement stacking (tickets + KB docs)
- Variant knowledge archive/restore on removal
- Variant lifecycle in period-end cron
- Paddle subscription items for variants
- Variant invoices with line items

**Day 3 Total: 10 items**

---

### DAY 4 — Netflix-Style Cancel Improvements + Data Lifecycle + Re-subscription
**Goal:** Perfect the cancel/reactivate flow. Handle data properly.

#### Cancel Flow Improvements:

| ID | Item | Details |
|----|------|---------|
| C1 | Cancel confirmation flow | Step 1: "Why are you leaving?" (feedback form). Step 2: Save offer — "Stay for 20% off next 3 months." Step 3: Clear consequences: "You'll keep access until [date]. After that: agents paused, data archived in 30 days." Step 4: Final confirm |
| C2 | Auto-pay removal vs cancel | Two separate actions: (a) "Remove auto-pay" — keeps subscription active until period end, then doesn't renew. Same as cancel-at-period-end. (b) "Cancel immediately" — stops service now, no refund. Both options clearly labeled |
| C3 | Period-end service stop | When cancel period ends: (a) Pause all AI agents, (b) Disable team member access (except admin), (c) Disable all channels (email, SMS, chat, voice), (d) Dashboard becomes read-only, (e) Data export available |
| C4 | 30-day data retention after cancel | After service stops: data preserved for 30 days. Counter shown on login: "Your data will be permanently deleted in 23 days. Export now." Daily email reminder for first 7 days |
| C5 | Data export before/during cancel | `GET /api/export/company-data` — exports all company data: tickets, customers, conversations, KB docs, settings, audit logs. Available as ZIP (JSON + CSV files). Async generation with download link |
| C6 | Data retention policy cron | Daily cron: check for canceled subscriptions where `service_stopped_at + 30 days <= today`. Execute data cleanup: soft-delete tickets, anonymize customer PII (GDPR right to erasure), archive KB docs, retain only billing records (7-year retention for financial compliance) |
| C7 | Hard delete after retention | After retention period: delete non-financial data permanently. Keep: subscription records, invoices, payment records (legal requirement). Log the deletion in audit trail |

#### Re-subscription Flow:

| ID | Item | Details |
|----|------|---------|
| R1 | Re-subscribe within retention period | If customer re-subscribes within 30 days of cancel: (a) Restore all data from archive, (b) Unpause agents, (c) Restore team access, (d) Reactivate channels, (e) Option to pick same or different plan |
| R2 | Re-subscribe after retention period | If > 30 days: fresh start. Previous data is gone (only financial records kept). Warn customer before they subscribe |
| R3 | Plan change on re-subscription | Can re-subscribe at any tier (not necessarily previous tier). If upgrading: immediate with proration. If downgrading: start fresh at lower tier |

#### Grace Period Improvements:

| ID | Item | Details |
|----|------|---------|
| G1 | Payment failure: immediate stop (no grace) | Confirmed: payment fails = service stops NOW. Fix email to say this. No 48-hour window. But keep the 7-day reactivation window (see below) |
| G2 | 7-day reactivation window after payment failure | After payment failure: customer has 7 days to update payment method. After 7 days: subscription canceled, enters 30-day data retention. During 7 days: can see dashboard (read-only) but agents are stopped |
| G3 | Auto-retry failed payments | Configure Paddle to auto-retry failed payments: Day 1 (immediate fail), Day 3 (auto-retry), Day 5 (auto-retry), Day 7 (final — cancel if still failing) |
| G4 | Payment method update | `POST /api/billing/payment-method` — redirect to Paddle portal for card update. After update: automatically retry the failed payment. If successful: resume service immediately |

**Day 4 Deliverables:**
- Complete cancel flow with feedback, save offer, consequences
- 30-day data retention after cancel
- Data export endpoint (full company data ZIP)
- Data retention cron with GDPR-compliant cleanup
- Re-subscription flow (within retention = restore data, after = fresh start)
- Payment failure: immediate stop + 7-day fix window
- Auto-retry on failed payments (Day 1, 3, 5, 7)
- Payment method update via Paddle portal

**Day 4 Total: 14 items**

---

### DAY 5 — Chargebacks + Refunds + Spending Caps + Webhook Hardening
**Goal:** Handle edge cases that protect PARWA from revenue loss.

#### Chargeback Handling:

| ID | Item | Details |
|----|------|---------|
| CB1 | Paddle chargeback webhook handler | Listen for `payment.chargeback.created` event. Create `Chargeback` record: transaction_id, amount, reason, status |
| CB2 | Immediate service stop on chargeback | Same as payment failure: stop agents, freeze tickets, disable channels. Flag account for review |
| CB3 | Chargeback notification | Email admin team: "Chargeback received: $2,499 from Acme Corp. Reason: Disputed charge." Include customer info, transaction details, link to review |
| CB4 | Chargeback reconciliation | Add to daily reconciliation task: cross-reference local transactions with Paddle. Flag discrepancies. Auto-resolve if Paddle confirms chargeback reversal |
| CB5 | Customer communication on chargeback | Don't auto-notify customer (legal sensitivity). Admin manually decides whether to contact. Template available: "We received a notification from your bank. Please contact support." |

#### Refund System (PARWA → Client):

| ID | Item | Details |
|----|------|---------|
| RF1 | Admin refund API | `POST /api/admin/refunds` — admin-only endpoint. Accept: company_id, amount, reason, type (full/partial/credit). Require approval from 2 admins for amounts > $500 |
| RF2 | Refund in Paddle | Use Paddle's refund API: create refund against original transaction. Support full and partial refunds |
| RF3 | Credit balance system | New model: `CreditBalance` — company_id, amount, currency, source (refund/promo/goodwill), expires_at. Apply credits to next invoice automatically |
| RF4 | 24-hour cooling-off refund | Within 24 hours of subscription creation: allow self-service refund request. Admin auto-approved for < $1,000. Creates Paddle refund, issues credit, cancels subscription |
| RF5 | Refund audit trail | Every refund logged in `ProrationAudit` with: original_amount, refund_amount, reason, approver, Paddle_refund_id. Immutable record |

#### Spending Caps:

| ID | Item | Details |
|----|------|---------|
| SC1 | Customer-configurable hard cap | `PATCH /api/billing/spending-cap` — customer sets max overage amount per period (e.g., $50/mo). Stored in company settings |
| SC2 | Hard cap enforcement | In overage processing: check `spending_cap - current_overage_charges`. If overage would exceed cap: skip the charge AND block new tickets (same as hard limit). Notify customer: "You've reached your $50 overage cap. New tickets are blocked. Upgrade your plan to continue." |
| SC3 | Soft cap alerts | Configurable thresholds: 50% of cap, 75% of cap, 90% of cap. Each triggers notification. "You've spent $25 of your $50 overage budget." |
| SC4 | No-cap option | Default: no spending cap (unlimited overage). Customer explicitly opts into a cap. Clear warning: "Setting a cap means AI will stop accepting tickets when limit is reached." |

#### Webhook Hardening:

| ID | Item | Details |
|----|------|---------|
| WH1 | Webhook backfill mechanism | New endpoint: `POST /api/admin/webhooks/backfill` — admin triggers. Fetches missed events from Paddle's API (`GET /events` with `since_timestamp`). Re-processes each event. Idempotency keys prevent double-processing |
| WH2 | Webhook health monitoring | Track: webhooks received, processed, failed, processing_time_ms. Alert if failure rate > 5% or processing time > 5s. Dashboard widget for webhook health |
| WH3 | Dead letter queue | Failed webhook processing goes to dead letter queue (DB table: `DeadLetterWebhook`). Admin can manually retry or discard. Auto-retry up to 3 times with exponential backoff |
| WH4 | Webhook ordering guarantee | `WebhookSequence` model already exists. Ensure events are processed in order. If event N+1 arrives before N: queue N+1, process N first, then N+1 |

#### Financial Safety:

| ID | Item | Details |
|----|------|---------|
| FS1 | Maximum overage cap | Global maximum: $500/month in overage per company regardless of customer cap setting. Prevents runaway charges from bugs or abuse |
| FS2 | Anomaly detection | Daily cron: if company's ticket volume suddenly triples vs previous day, flag for review. Could indicate: bug, abuse, misconfiguration. Alert admin team |
| FS3 | Invoice audit | Weekly cron: compare local invoices with Paddle invoices. Flag any discrepancies. Auto-sync on match, alert on mismatch |

**Day 5 Deliverables:**
- Chargeback handling (webhook, service stop, notification, reconciliation)
- Admin refund system with Paddle integration
- Credit balance system
- 24-hour cooling-off self-service refund
- Customer-configurable spending cap with hard stop
- Soft cap alerts at configurable thresholds
- Webhook backfill mechanism
- Webhook health monitoring + dead letter queue
- Global overage maximum ($500/mo)
- Anomaly detection for ticket volume spikes
- Invoice audit cron

**Day 5 Total: 20 items**

---

### DAY 6 — Missing Features + Testing + Dashboard Integration Prep
**Goal:** Fill remaining gaps, add polish, prepare for frontend.

#### Missing Features:

| ID | Feature | Details |
|----|---------|---------|
| MF1 | Trial period | New `trial_days` column on Subscription (default 0). During trial: full access, no charges. At trial end: first charge via Paddle. Trial-to-paid conversion tracking. Trial expiration reminder: 3 days, 1 day, expiry day |
| MF2 | Subscription pause | `POST /api/billing/pause` — temporary pause. Sets `status='paused'`. No charges during pause. Agents stopped, channels disabled. `POST /api/billing/resume` — unpause. Period end date extended by pause duration. Max pause: 30 days. 1 pause per 6 months |
| MF3 | Discount/promo codes | New model: `PromoCode` — code, discount_type (percentage/fixed), discount_value, max_uses, used_count, valid_from, valid_until, applies_to_tiers. `POST /api/billing/apply-promo` — validate and apply. First invoice gets discount |
| MF4 | Multi-currency preparation | Add `currency` column to Company model. Default: USD. In all money calculations: use `Decimal` with currency context. Store original currency and USD equivalent. Paddle handles conversion — PARWA stores in customer's currency. Phase 1: USD only with currency field ready. Phase 2: enable EUR, GBP via Paddle |
| MF5 | Company timezone for billing | Use company's timezone setting for: period start/end display, invoice date display, usage warning timing. Internal storage still UTC. Display in company timezone. Fix billing period display |
| MF6 | Corporate/B2B invoicing | For enterprise customers: manual invoicing option. Admin creates invoice manually, marks as paid when PO received. Bypass Paddle auto-billing. New `billing_method` column: `automatic` (default) or `manual`. Invoice PDF shows payment terms: "Net 30" |
| MF7 | Invoice amendments | `POST /api/admin/invoices/{id}/amend` — admin-only. Create amendment record: original amount, new amount, reason. Issue credit or additional charge. Paddle credit note API |
| MF8 | Spending analytics | `GET /api/billing/analytics` — returns: monthly spend, overage costs, variant costs, projected next month. Per-channel breakdown: email tickets cost, chat tickets cost, voice minutes cost, SMS cost. Trend data for 6 months |
| MF9 | Budget alerts (dollar amount) | Beyond 80% ticket quota warning: add dollar amount alerts. "You've spent $1,800 of your $2,499 plan this month. Projected total: $2,750." Alert at: 50%, 75%, 90%, 100% of plan price |
| MF10 | Voice minute metering | Track voice minutes used per period. `UsageRecord.voice_minutes_used` — hook into voice channel service. If voice minutes exceed plan limit: per-minute overage charge ($0.05/min). Voice minutes NOT metered in Phase 1 — just track and display. Phase 2: add charges |
| MF11 | SMS cost tracking | Track SMS count per period. `UsageRecord.sms_sent`. Hook into SMS channel service. Display in billing dashboard. Pass-through cost from Twilio. Phase 1: track only. Phase 2: charge pass-through |
| MF12 | Payment failure reconciliation | Fix `reconciliation_tasks.py` using `shared_task` — change to `app.task` for consistency with rest of codebase. Fix sync Paddle client monkey-patching |

#### Testing:

| ID | Test | Details |
|----|------|---------|
| T1 | Billing cycle tests | Monthly: create, 30 days, renew, usage resets. Yearly: create, 365 days, renew. Edge: leap year, period-end on weekend |
| T2 | Upgrade/downgrade tests | Mid-month upgrade: proration correct, limits apply immediately. Downgrade: scheduled, executes at period end, resources cleaned |
| T3 | Variant tests | Add variant: proration, limits stack. Remove variant: at period end, knowledge archived. Re-add: knowledge restored |
| T4 | Overage tests | Hit limit: overage charges correct ($0.10/ticket). Spending cap: blocks at cap. No cap: unlimited overage. Double-counting: verify fixed |
| T5 | Cancel/reactivate tests | Cancel at period end: access until end. Immediate cancel: access stops. Reactivate within retention: data restored. Reactivate after retention: fresh start |
| T6 | Payment failure tests | Payment fails: immediate stop. Update payment: resume. 7-day no fix: canceled. Chargeback: stopped + flagged |
| T7 | Edge case tests | Concurrent plan changes, webhook duplicates, Paddle timeouts, Redis down during idempotency check, partial overage processing |
| T8 | Paddle integration tests | Sandbox environment: create subscription, upgrade, cancel, overage charge, refund. Verify all Paddle API calls work |

#### Dashboard Integration Preparation:

| ID | Item | Details |
|----|------|---------|
| DI1 | Billing status API | `GET /api/billing/dashboard-summary` — returns everything dashboard needs: current plan, usage (tickets/agents/team/KB/voice), period dates, next invoice date, overage status, spending cap. Single API call for dashboard billing widget |
| DI2 | Plan comparison API | `GET /api/billing/plan-comparison` — returns all tiers with features, prices (monthly/yearly), and what customer would gain/lose by switching |
| DI3 | Variant catalog API | `GET /api/billing/variant-catalog` — returns all available industry variants with prices, features, ticket additions. Customer's active variants marked |
| DI4 | Invoice history API enhancement | Enhance existing `GET /invoices` with: running total, year-to-date spend, downloadable CSV of all invoices |
| DI5 | Payment schedule API | `GET /api/billing/payment-schedule` — returns: next payment date, next payment amount, upcoming charges (overage, variants), projected monthly total |

**Day 6 Deliverables:**
- Trial period support
- Subscription pause/resume
- Promo code system
- Multi-currency preparation
- Company timezone for billing display
- Corporate/B2B invoicing option
- Invoice amendments
- Spending analytics + budget alerts
- Voice/SMS usage tracking (Phase 1: track only)
- Reconciliation task fixes
- 8 test suites covering all scenarios
- 5 dashboard-ready API endpoints

**Day 6 Total: 25 items**

---

## COMPLETE ITEM SUMMARY

| Day | Focus | Items | Cumulative |
|-----|-------|-------|------------|
| Day 1 | Critical bugs, usage metering, entitlement enforcement | 18 | 18 |
| Day 2 | Downgrade execution, yearly billing, 30-day periods | 18 | 36 |
| Day 3 | Variant add-on management, mid-year variant purchase | 10 | 46 |
| Day 4 | Cancel/reactivate, data lifecycle, Netflix improvements | 14 | 60 |
| Day 5 | Chargebacks, refunds, spending caps, webhook hardening | 20 | 80 |
| Day 6 | Missing features, testing, dashboard API prep | 25 | 105 |

**Total: 105 items across 6 days**

---

## ALL 43 ISSUES COVERAGE MAP

| # | Issue | Severity | Day | Item ID |
|---|-------|----------|-----|---------|
| 1 | Downgrades never executed | 🔴 Critical | 2 | D1-D3 |
| 2 | No resource cleanup on downgrade | 🔴 Critical | 2 | D4 |
| 3 | Industry variants disconnected from billing | 🔴 Critical | 1 | E4-E5, 3 | V1-V10 |
| 4 | Usage metering not hooked to ticket lifecycle | 🔴 Critical | 1 | M1-M2 |
| 5 | Calendar month vs billing period mismatch | 🔴 Critical | 1 | M3-M4 |
| 6 | No refund system for subscriptions | 🟠 High | 5 | RF1-RF5 |
| 7 | No entitlement enforcement (most resources) | 🟠 High | 1 | E1-E3 |
| 8 | No voice/SMS/email metering | 🟠 High | 6 | MF10-MF11 |
| 9 | No chargeback handling | 🟠 High | 5 | CB1-CB5 |
| 10 | Middleware fail-open | 🟠 High | 1 | E1 |
| 11 | No webhook backfill | 🟡 Medium | 5 | WH1 |
| 12 | No data export before cancel | 🟡 Medium | 4 | C5 |
| 13 | No data retention policy | 🟡 Medium | 4 | C4, C6-C7 |
| 14 | No re-subscription flow | 🟡 Medium | 4 | R1-R3 |
| 15 | USD only | 🟡 Medium | 6 | MF4 |
| 16 | UTC only for billing dates | 🟡 Medium | 6 | MF5 |
| 17 | No spending cap | 🟡 Medium | 5 | SC1-SC4 |
| 18 | No corporate/B2B invoicing | 🟡 Medium | 6 | MF6 |
| 19 | No invoice amendments | 🟡 Medium | 6 | MF7 |
| 20 | No credit balance system | 🟡 Medium | 5 | RF3 |
| 21 | No trial period | 🟡 Medium | 6 | MF1 |
| 22 | No promo codes | 🟡 Medium | 6 | MF3 |
| 23 | No subscription pause | 🟡 Medium | 6 | MF2 |
| 24 | Reactivation only during grace period | 🟡 Medium | 4 | R1-R3 |
| 25 | No variant removal flow | 🟡 Medium | 3 | V3, V7-V8 |
| 26 | Variant knowledge not cleaned | 🟡 Medium | 3 | V8 |
| 27 | Edge month handling | 🟡 Medium | 2 | P1-P5 |
| 28 | No spending analytics per channel | 🟢 Low | 6 | MF8 |
| 29 | No budget alerts ($ amount) | 🟢 Low | 6 | MF9 |
| 30 | In-memory idempotency | 🟢 Low | 1 | B8 |
| 31 | ReAct billing tool wrong plan names | 🟢 Low | 1 | B7 |
| 32 | Two HMAC implementations | 🟢 Low | 1 | B6 |
| 33 | Paddle env switching not automated | 🟢 Low | 6 | T8 |
| B1 | Email says 48hr, code says immediate | High | 1 | B3 |
| B2 | create_transaction missing | Critical | 1 | B1 |
| B3 | Double-counting overage | Critical | 1 | B2 |
| B4 | Agents not stopped on payment fail | High | 1 | B4 |
| B5 | Ticket status lost on resume | Medium | 1 | B5 |
| B6 | Unknown variant IDs fake price IDs | Medium | 1 | M5 |
| B7 | shared_task vs app.task | Low | 6 | MF12 |
| B8 | Payment method update endpoint | 🟡 Medium | 4 | G4 |
| — | Yearly billing | 🟡 Medium | 2 | Y1-Y7 |
| — | Exact 30-day periods | 🟡 Medium | 2 | P1-P5 |
| — | Variant add-on management | 🟡 Medium | 3 | V1-V10 |
| — | Mid-year variant proration | 🟡 Medium | 3 | V5 |
| — | Netflix cancel improvements | 🟡 Medium | 4 | C1-C7 |
| — | Spending cap enforcement | 🟡 Medium | 5 | SC1-SC4 |
| — | Webhook dead letter queue | 🟡 Medium | 5 | WH3 |

---

## BACKEND FILES TO MODIFY

| File | Changes |
|------|---------|
| `paddle_client.py` | Add `create_transaction()`, standardize HMAC |
| `overage_service.py` | Fix double-counting, fix price ID, align to billing period |
| `payment_failure_service.py` | Fix email copy (48hr → immediate) |
| `payment_failure_tasks.py` | Fix agent stop, fix ticket status restore |
| `subscription_service.py` | Add yearly frequency, 30-day periods, variant add-ons |
| `proration_service.py` | Use 30-day divisor, add yearly proration |
| `paddle_service.py` | Fix variant price IDs, move idempotency to Redis |
| `pricing_service.py` | Add yearly pricing, variant stacking logic |
| `billing_tool.py` | Fix plan names, connect to real billing (not mock) |
| `billing_webhooks.py` | Add chargeback handler, fix HMAC, standardize |
| `variant_check.py` (middleware) | Fix fail-open, enforce ALL resources |
| `variant_limit_service.py` | Read from DB not hardcoded, add stacking |
| `billing_tasks.py` | Add period-end cron, downgrade execution, retention cron |
| `reconciliation_tasks.py` | Fix shared_task, add invoice audit |
| `schemas/billing.py` | Add yearly frequency, spending cap, variant models |
| `database/models/billing.py` | Add billing_frequency, CompanyVariant, CreditBalance |
| `database/models/billing_extended.py` | Add Chargeback, DeadLetterWebhook, PromoCode |
| NEW: `refund_service.py` | Admin refund system, credit balance |
| NEW: `chargeback_service.py` | Chargeback handling |
| NEW: `data_retention_service.py` | Post-cancel data lifecycle |
| NEW: `trial_service.py` | Trial period management |
| NEW: `promo_service.py` | Promo code validation and application |
| NEW: `spending_cap_service.py` | Hard/soft cap enforcement |

---

## DEPENDENCIES

| Dependency | Part | Impact |
|------------|------|--------|
| Dashboard billing UI | Part 12 | Day 6 prepares 5 dashboard-ready APIs. Actual UI built in Part 12 Day 7 |
| AI agents stop/resume | Part 12 (Agents) | Payment failure task needs to actually stop agents — requires agent service connection |
| Voice channel metering | Part 14 | Voice minute tracking hooks into voice channel service |
| GDPR right to erasure | Part 18 | Data retention policy aligns with Part 18 GDPR endpoint |

---

## VERIFICATION CHECKLIST (after all 6 days)

- [ ] Usage metering auto-increments on ticket creation
- [ ] Overage charges calculate correctly (no double-counting)
- [ ] Downgrade executes at period end via cron
- [ ] Extra agents paused on downgrade
- [ ] Extra team members downgraded on downgrade
- [ ] Extra KB docs archived on downgrade
- [ ] Yearly billing creates 365-day periods
- [ ] 30-day billing periods work for all months
- [ ] Variant add-on increases ticket limit immediately
- [ ] Variant removal archives knowledge data
- [ ] Mid-year variant purchase charges correct proration
- [ ] Cancel: access until period end, data 30-day retention
- [ ] Data export ZIP available during retention
- [ ] Re-subscribe within 30 days: data restored
- [ ] Payment failure: immediate stop, 7-day fix window
- [ ] Chargeback: handled, service stopped, admin notified
- [ ] Refund: admin can issue, credit balance works
- [ ] Spending cap: blocks tickets when exceeded
- [ ] Soft cap alerts fire at 50/75/90% thresholds
- [ ] Webhook backfill works after downtime
- [ ] Dead letter queue captures failed webhook processing
- [ ] Trial period: full access, converts to paid
- [ ] Subscription pause: stops billing and service
- [ ] All 8 test suites pass
- [ ] Paddle sandbox integration tests pass
