"""
PARWA Variant Pipeline — FULL Manual Test (100 Tickets × 3 Variants)

Tests ALL 30 frameworks/engines across all 3 variant tiers:
  - mini_parwa (Starter): 10 nodes, Tier 1 frameworks
  - parwa (Growth): 22 nodes, Tier 1+2 frameworks
  - parwa_high (High): 27 nodes, ALL frameworks

Framework Coverage Map:
  Tier 1 (Always Active): CLARA, CRP, GSD, Smart Router, Technique Router, Confidence Scoring
  Tier 2 (Growth+): CoT, Reverse Thinking, ReAct, Step-Back, ThoT
  Tier 3 (High only): GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most
  Enrichment: Emotional Intelligence, Churn Retention, Billing Intelligence, Tech Diagnostics, Shipping Intelligence
  Supporting: TRIVYA, MAKER/FAKE, DSPy, Agent Lightning, Graceful Escalation, Loophole Detection

Channel Coverage: chat, email, sms, voice, social
Industry Coverage: ecommerce, saas, logistics, general

Usage:
  cd /home/z/my-project/parwa/backend
  python -m app.test_all_variants_100
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── Add backend to path ──
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

# ── Configure LLM Provider (ZAI Gateway for testing, falls back to templates) ──
os.environ.setdefault("LLM_PROVIDER", "zai_gateway")

# ══════════════════════════════════════════════════════════════════
# 100 REALISTIC CUSTOMER SUPPORT TICKETS
# Covering: ALL industries, ALL channels, ALL framework triggers,
# multi-step, tough, edge cases, VIP, billing, technical, emotional,
# compliance, emergency, loophole, escalation scenarios
# ══════════════════════════════════════════════════════════════════

TICKETS: List[Dict[str, Any]] = [
    # ─── TIER 1 FRAMEWORK TRIGGERS (CLARA, CRP, GSD, Smart Router, Confidence) ───
    # Simple requests that should use Tier 1 only on mini_parwa

    # 1-5: GSD State Machine — greeting → understanding → resolving
    {"id": 1, "subject": "How do I reset my password?", "message": "Hi, I forgot my password and can't log in. Can you help me reset it? I've tried clicking the forgot password link but I'm not getting the email.", "category": "account", "priority": "medium", "channel": "chat", "industry": "saas", "customer_tier": "free", "expected_frameworks": ["GSD", "CLARA", "CRP"]},
    {"id": 2, "subject": "Where is my order?", "message": "Hello, I placed an order 5 days ago and haven't received any shipping confirmation. Order number is #EC-8834. Can you check the status?", "category": "order_tracking", "priority": "medium", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["GSD", "CLARA", "CRP", "Shipping Intelligence"]},
    {"id": 3, "subject": "Change my delivery address", "message": "I need to change my delivery address for my pending order. The new address is 456 Oak Avenue, Apt 12B, Mumbai 400001. Order #LG-2291.", "category": "address_change", "priority": "medium", "channel": "chat", "industry": "logistics", "customer_tier": "free", "expected_frameworks": ["GSD", "CLARA", "CRP"]},
    {"id": 4, "subject": "Store timings for tomorrow", "message": "What are your store hours for tomorrow? I want to visit for a product pickup.", "category": "general", "priority": "low", "channel": "sms", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["GSD", "CLARA", "CRP"]},
    {"id": 5, "subject": "Do you offer international shipping?", "message": "I want to order from UAE. Do you ship internationally? What are the costs and delivery times?", "category": "general", "priority": "low", "channel": "chat", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["GSD", "CLARA", "CRP"]},

    # 6-10: CLARA Quality Gate — needs structured, logical, brand-aligned response
    {"id": 6, "subject": "Product compatibility question", "message": "I have a MacBook Pro M2. Will your USB-C dock station work with it? The specs page isn't clear about M-series chip compatibility.", "category": "product_info", "priority": "low", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["CLARA", "CRP", "GSD"]},
    {"id": 7, "subject": "How to apply a discount code", "message": "I have a promo code SAVE20 but I can't find where to enter it during checkout. The cart page doesn't show a promo code field.", "category": "general", "priority": "low", "channel": "chat", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["CLARA", "CRP", "GSD"]},
    {"id": 8, "subject": "Warranty information request", "message": "What does the 2-year warranty cover? I just bought a monitor and want to understand what's included before I register the product.", "category": "warranty", "priority": "low", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["CLARA", "CRP", "GSD"]},
    {"id": 9, "subject": "Account verification email not received", "message": "Signed up 30 minutes ago but the verification email hasn't arrived. Checked spam folder too. My email is john.doe@company.org", "category": "account", "priority": "medium", "channel": "chat", "industry": "saas", "customer_tier": "free", "expected_frameworks": ["CLARA", "CRP", "GSD", "Tech Diagnostics"]},
    {"id": 10, "subject": "Bulk order discount inquiry", "message": "We want to order 200 units of the wireless keyboard for our office. Do you offer volume discounts? What's the best price you can do?", "category": "general", "priority": "medium", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["CLARA", "CRP", "GSD"]},

    # ─── TIER 2 FRAMEWORK TRIGGERS (CoT, Reverse Thinking, ReAct, Step-Back, ThoT) ───
    # Complex, multi-step, low-confidence — triggers on parwa (Growth) and above

    # 11-15: Chain of Thought (R1: complexity > 0.4, R14: technical intent)
    {"id": 11, "subject": "API integration returning 403 intermittently", "message": "Our production integration with your API is returning 403 Forbidden errors about 30% of the time. We've verified our API key is valid, the rate limit is not hit (we're at 200 requests/minute, limit is 1000), and the endpoints work fine when tested from Postman. The errors started after we migrated our servers from us-east-1 to ap-south-1. We're using OAuth2 with client_credentials flow. The 403s seem to correlate with our peak traffic window (9-11 AM IST). Could this be a geo-restriction or a token refresh race condition?", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "ReAct", "Tech Diagnostics", "CLARA"]},
    {"id": 12, "subject": "Database migration failing with constraint violation", "message": "We're trying to migrate from your v2 API to v3 but the migration script keeps failing with a foreign key constraint violation on the 'orders' table. The documentation says v3 supports backward compatibility but we're getting data integrity errors. We have 500K+ records that need migration. The error specifically says: 'SQLSTATE 23503: insert or update on table \"orders\" violates foreign key constraint'. Can you walk us through the correct migration procedure?", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "ReAct", "Tech Diagnostics"]},
    {"id": 13, "subject": "Webhook payload schema changed without notice", "message": "Our webhook handler started failing this morning because the payload schema changed. The 'customer' field is now nested under 'data.customer' instead of being at the root level. Also, the 'event_type' field has been renamed to 'type'. This broke our entire order processing pipeline. We have 200+ unprocessed events in the queue. Why wasn't this communicated? How do we handle both old and new formats?", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "ReAct", "CLARA"]},
    {"id": 14, "subject": "SSO SAML assertion parsing error after cert rotation", "message": "After rotating our IdP certificate yesterday, our SSO integration with your platform broke. The SAML assertion is being rejected with 'InvalidSignature' error. We've updated the x509 certificate in the SSO settings, but the old certificate fingerprint seems cached. We have 800 employees locked out. Cleared browser cache, tried incognito, restarted IdP service — nothing works. This is blocking our entire organization.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "ReAct", "Step-Back", "Tech Diagnostics"]},
    {"id": 15, "subject": "Multi-region deployment latency spike investigation", "message": "Our application deployed across 3 regions (us-east, eu-west, ap-south) is experiencing 5-10 second latency spikes every 15 minutes when accessing your API. The spikes don't correlate with our traffic patterns. We've checked our infrastructure — no CPU/memory issues, no network bottlenecks. The latency appears on both read and write endpoints. Could this be related to your internal database replication or cache invalidation cycles? We need root cause analysis.", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "ReAct", "Tech Diagnostics", "CLARA"]},

    # 16-20: Reverse Thinking (R2: confidence < 0.7) — ambiguous, tricky scenarios
    {"id": 16, "subject": "Charged for free trial — is this a scam?", "message": "I signed up for a 14-day free trial but I was charged $49.99 on the same day! Your website clearly says 'No credit card required for trial'. This feels like a scam. I want my money back immediately and I'm reporting this to my bank as fraud unless this is resolved within 24 hours. I also saw similar complaints on Reddit about your company.", "category": "billing", "priority": "critical", "channel": "chat", "industry": "saas", "customer_tier": "free", "expected_frameworks": ["Reverse Thinking", "Step-Back", "Emotional Intelligence", "Billing Intelligence", "CLARA"]},
    {"id": 17, "subject": "Refund approved 3 weeks ago but money never arrived", "message": "Your team approved my refund of $389 on March 1st and I received a confirmation email with reference number REF-78234. It's now March 22nd and the money has NOT appeared in my account. I've called my bank twice and they say no refund is pending. Your support agent on chat said 'it's been processed' but clearly it hasn't. I need proof of the refund transfer — the transaction ID from your payment processor — so my bank can trace it.", "category": "refunds", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Reverse Thinking", "Billing Intelligence", "Emotional Intelligence"]},
    {"id": 18, "subject": "Product I received is counterfeit", "message": "I ordered a Sony WH-1000XM5 headphone from your site but the product I received is clearly fake. The packaging looks off, the sound quality is terrible, and the serial number on the box doesn't match the one on Sony's warranty checker. I paid $349 for what was advertised as genuine. This is extremely concerning — are you selling counterfeit products? I want a full refund and an explanation of your supply chain verification process.", "category": "returns", "priority": "critical", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Reverse Thinking", "Emotional Intelligence", "CLARA", "Loophole Detection"]},
    {"id": 19, "subject": "Medical device delivery delayed — health at risk", "message": "My CPAP machine order has been stuck in transit for 2 weeks. I have severe sleep apnea and cannot sleep without it. Your website promised 3-day delivery for medical devices. This isn't just inconvenience — my health is deteriorating. I've been to the ER twice this week due to sleep deprivation complications. I need this escalated to the highest priority possible.", "category": "logistics", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Reverse Thinking", "Emergency Detection", "Emotional Intelligence", "Graceful Escalation"]},
    {"id": 20, "subject": "Data breach notification — customer data exposed", "message": "One of our customers reported seeing another company's data when they logged into our dashboard. We use your platform to store PII. If there's a data isolation breach on your end, this is a GDPR Article 33 violation — we have 72 hours to notify our DPA. We need immediate confirmation: is there a data breach? What data may have been exposed? What remediation steps are you taking?", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Reverse Thinking", "Emergency Detection", "Graceful Escalation", "CLARA"]},

    # 21-25: ReAct (R7: external data needed, R14: technical intent)
    {"id": 21, "subject": "Real-time inventory sync showing wrong stock levels", "message": "Your inventory API is returning stock levels that don't match what's actually in our warehouse. The API shows 150 units of SKU-4482 but our warehouse management system shows 47. This discrepancy has caused us to oversell 103 units — customers are getting 'out of stock' emails after placing orders. We need the inventory sync fixed immediately and a reconciliation report for all SKUs.", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "ecommerce", "customer_tier": "pro", "expected_frameworks": ["ReAct", "CoT", "Shipping Intelligence", "Tech Diagnostics"]},
    {"id": 22, "subject": "Custom report builder throwing timeout errors", "message": "When I try to generate a report with more than 10K rows and 15 columns, the report builder times out after 30 seconds. I need these reports for our monthly board meeting. I've tried filtering by date range and reducing columns but even 5K rows × 10 columns sometimes times out. Our data volume is growing and this feature is becoming unusable. What's the maximum supported dataset size?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["ReAct", "CoT", "Tech Diagnostics"]},
    {"id": 23, "subject": "Shipment tracking shows city 500km away from my address", "message": "My package tracking shows it was delivered to a city 500km from where I live. The delivery confirmation photo shows a building I've never seen. Your system says 'delivered successfully' but I don't have the package. Order #LG-9923 was supposed to come to Bangalore but shows delivered in Hyderabad. How does this even happen?", "category": "logistics", "priority": "critical", "channel": "chat", "industry": "logistics", "customer_tier": "free", "expected_frameworks": ["ReAct", "Shipping Intelligence", "Emotional Intelligence"]},
    {"id": 24, "subject": "Payment gateway integration returning duplicate charges", "message": "Our customers are being double-charged for the same transaction. We're using your Stripe integration and seeing duplicate charge IDs in our logs. This started after your platform update last Thursday. We've had 47 customer complaints in 3 days. We need this fixed NOW and we need a way to identify and automatically refund all duplicate charges. Our reputation is being damaged.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["ReAct", "Billing Intelligence", "CoT", "Graceful Escalation"]},
    {"id": 25, "subject": "Email automation sending campaigns at wrong times", "message": "Our automated email campaigns scheduled for 9 AM local time are being sent at 3 AM instead. The timezone settings in our account show IST (UTC+5:30) correctly, but the actual send times suggest UTC is being used. This has destroyed our open rates — from 28% down to 4%. We have 50K subscribers getting emails in the middle of the night.", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["ReAct", "CoT", "Tech Diagnostics"]},

    # 26-30: Step-Back (R2: confidence < 0.7, R12: reasoning loop)
    {"id": 26, "subject": "Subscription charged but account shows free tier", "message": "I upgraded to the Pro plan 5 days ago and my credit card was charged $79/month. But when I log in, my account still shows 'Free Plan' and I can't access Pro features. I've tried logging out and back in, clearing cache, using different browsers — nothing works. It's like the payment went through but the upgrade didn't. Very confused and frustrated.", "category": "billing", "priority": "critical", "channel": "chat", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Step-Back", "Reverse Thinking", "Billing Intelligence"]},
    {"id": 27, "subject": "Returned item but got someone else's return confirmation", "message": "I returned my wireless earbuds last week, but the return confirmation email I received mentions a completely different product (a coffee machine!) and a different customer's name and address. This means either my return got mixed up with someone else's, or your system is sending wrong confirmations. Either way, I'm worried about my refund. Can you verify my actual return status?", "category": "returns", "priority": "critical", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Step-Back", "Reverse Thinking", "CLARA"]},
    {"id": 28, "subject": "Cancelled subscription but still getting charged AND getting cancellation emails", "message": "This is bizarre — I cancelled my subscription last month, received the cancellation confirmation email, but I'm STILL being charged every month. And every month I also get an email saying my subscription has been cancelled. So your system knows I cancelled but still charges me? I've been on 4 chat sessions and each time they say 'it's fixed now' but it isn't. This has been going on for 3 months!", "category": "billing", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Step-Back", "Reverse Thinking", "Billing Intelligence", "Emotional Intelligence", "Graceful Escalation"]},
    {"id": 29, "subject": "Account shows two different subscription statuses simultaneously", "message": "When I go to Settings, it says I'm on the Enterprise plan. When I go to Billing, it says I'm on Starter. When I try to use Enterprise features, I get 'upgrade required' errors. When I try to downgrade, it says 'you are already on Starter'. My team is completely confused. We're paying for Enterprise ($299/month) but can only use Starter features. Three support tickets already closed as 'resolved' but nothing changed.", "category": "billing", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Step-Back", "Reverse Thinking", "Billing Intelligence", "CoT"]},
    {"id": 30, "subject": "AI chatbot gave wrong product advice — now my device is broken", "message": "Your AI chatbot told me to update my router firmware using the wrong file. I followed the instructions exactly and now my router is bricked — won't turn on at all. The chatbot said 'download the AC3200 firmware' but I have the AC2400 model. This is going to cost me $200 for a new router. Your AI gave incorrect advice that damaged my property. I need compensation.", "category": "complaint", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Step-Back", "Emotional Intelligence", "Loophole Detection", "CLARA"]},

    # 31-35: Thread of Thought (R6: turns > 5) — long conversation scenarios
    {"id": 31, "subject": "7th follow-up: Return still not processed after 45 days", "message": "This is my 7th message about the same return. Timeline: Day 1 - I requested return. Day 5 - You approved it. Day 8 - I shipped the item. Day 12 - You received it (tracking confirmed). Day 15 - Agent said refund in 5-7 days. Day 22 - No refund, agent said 'processing'. Day 29 - Agent said 'escalated to finance'. Day 36 - Agent said 'approved, wait 3 days'. Day 42 - Still nothing. It's now Day 45 and I'm DONE being patient. $479.99 refund, order #EC-11234. This is unacceptable.", "category": "refunds", "priority": "critical", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["ThoT", "Step-Back", "Emotional Intelligence", "Billing Intelligence", "Graceful Escalation"]},
    {"id": 32, "subject": "Ongoing email thread: Team of 50 locked out for 3rd day", "message": "Day 3 update on the SSO outage affecting our entire 50-person team. Summary so far: Monday 9AM - SSO broke. Monday 11AM - Ticket #4521 opened. Monday 3PM - Agent said 'looking into it'. Tuesday - No update. Wednesday 10AM - I called, was told it's a 'known issue with the certificate update'. Wednesday 3PM - STILL NOT FIXED. Each person on my team has tried: clearing cache, different browsers, incognito, mobile app — nothing works. We're losing $15K/day in productivity.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["ThoT", "CoT", "ReAct", "Tech Diagnostics", "Graceful Escalation"]},
    {"id": 33, "subject": "6th attempt: Wrong items keep arriving", "message": "I've now received wrong items THREE times for the same order. Order history: 1st delivery - got blue instead of black. 2nd delivery (replacement) - got wrong size. 3rd delivery (second replacement) - got a completely different product. Each time your agent assures me it's been 'fixed in the warehouse'. I've now spent 4 weeks trying to get a simple black jacket in size M. This is beyond incompetence. I want the correct item expedited overnight AND a full refund for the inconvenience.", "category": "returns", "priority": "critical", "channel": "chat", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["ThoT", "Emotional Intelligence", "Reverse Thinking", "Shipping Intelligence"]},
    {"id": 34, "subject": "Recurring billing error month after month", "message": "This is the 4th consecutive month with incorrect billing. Month 1: Charged for 25 seats, we have 15. Agent gave credit. Month 2: Same error. Agent gave credit + promised fix. Month 3: STILL wrong. Agent escalated. Month 4 (NOW): Still being charged for 25 seats. Each month I waste 2 hours on support. I've now spent 8 hours total on an error your team keeps promising to fix. When will this actually be resolved permanently?", "category": "billing", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["ThoT", "Billing Intelligence", "Step-Back", "Emotional Intelligence"]},
    {"id": 35, "subject": "5th follow-up: Data export for legal discovery deadline tomorrow", "message": "I first requested a complete data export 2 weeks ago for a legal discovery deadline. The deadline is TOMORROW. Each time I follow up, I'm told: 'it's in the queue', 'processing large datasets takes time', 'you'll get an email when it's ready'. I've received nothing. If I miss this court deadline, our company faces potential sanctions. This is not optional — it's a legal obligation. I need that export TODAY, even if it's partial.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["ThoT", "Reverse Thinking", "Graceful Escalation", "Emergency Detection"]},

    # ─── TIER 3 FRAMEWORK TRIGGERS (High Only: GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most) ───

    # 36-40: Self-Consistency (R5: monetary > $100, R13: billing intent)
    {"id": 36, "subject": "Enterprise contract overcharge — $12,500 discrepancy", "message": "Our annual enterprise contract states $125,000/year for 500 seats. Our latest invoice is for $137,500 — a $12,500 overcharge. Upon investigation: 1) We're being billed for 550 seats instead of 500 (we have 487 active users). 2) The per-seat rate is $250 instead of the contracted $230. 3) A 'premium support add-on' of $2,500 is included that we never authorized. We need this invoice corrected before our AP department processes it on Friday. Please also audit all previous invoices for the same errors.", "category": "billing", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["Self-Consistency", "Billing Intelligence", "CoT", "CLARA"]},
    {"id": 37, "subject": "Refund of $2,400 for service outage — SLA violation", "message": "Per our SLA, you guarantee 99.95% uptime. Last month we experienced 4 hours of downtime, which puts you at 99.44%. Our contract stipulates a 10x credit for downtime beyond the SLA threshold. 4 hours of downtime at our monthly fee of $5,000 means we're owed $2,400 in credits. I need this credit applied to next month's invoice immediately, plus a root cause analysis of the outage.", "category": "billing", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["Self-Consistency", "Billing Intelligence", "CoT"]},
    {"id": 38, "subject": "Double charged $899 for annual subscription", "message": "I was charged $899 twice for my annual Pro subscription on the same day. Two separate charges on my credit card statement from your payment processor. Same amount, same date, same description. My account only shows one active subscription. I need the duplicate charge of $899 refunded immediately and confirmation that this won't happen again at next renewal.", "category": "billing", "priority": "critical", "channel": "chat", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Self-Consistency", "Billing Intelligence"]},
    {"id": 39, "subject": "Partial refund calculation wrong — $670 difference", "message": "I cancelled my annual subscription ($1,200/year) after 4 months. Your refund policy says 'proportional refund for unused months'. That should be 8/12 × $1,200 = $800. But the refund you processed is only $130. Your agent said it's because 'the first 3 months are non-refundable' and 'setup fees are deducted'. None of this is in our contract. I need the correct refund of $800 processed immediately.", "category": "billing", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Self-Consistency", "Billing Intelligence", "Reverse Thinking", "Loophole Detection"]},
    {"id": 40, "subject": "Tax miscalculation on $50K enterprise invoice", "message": "Our quarterly invoice for $50,000 shows 18% GST ($9,000) but we're registered under the composition scheme which caps GST at 6% for our category. We've submitted our GST certificate (GSTIN: 27AAACR5055K1ZG) multiple times. Your system keeps applying standard rate instead of our reduced rate. Over the past year, we've been overcharged approximately $24,000 in excess tax. We need all invoices reissued with correct tax and the excess refunded.", "category": "billing", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["Self-Consistency", "Billing Intelligence", "CoT", "CLARA"]},

    # 41-45: UoT / Tree of Thoughts (R3: VIP customer, R8: ≥3 resolution paths)
    {"id": 41, "subject": "VIP: Complete platform migration with zero downtime required", "message": "We're your largest enterprise client ($500K ARR). We need to migrate from your US data center to your EU data center to comply with GDPR data residency requirements. Requirements: 1) Zero downtime during migration. 2) All 2M+ customer records migrated with no data loss. 3) All integrations (Salesforce, HubSpot, Zendesk, Slack) must continue working during and after migration. 4) Rollback plan if anything goes wrong. 5) Complete by end of Q2. We need a detailed migration plan, timeline, and dedicated project manager.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["UoT", "ToT", "GST", "CoT", "ReAct"]},
    {"id": 42, "subject": "VIP: Custom AI model training on our proprietary data", "message": "As your Platinum partner, we want to train a custom AI model on our 10 years of customer interaction data (5M+ conversations). The model must: 1) Understand our industry-specific terminology. 2) Handle our 47 product categories with 95%+ accuracy. 3) Support 12 languages. 4) Comply with our data privacy policy (no data retention by the AI provider). 5) Deploy within our VPC. Can your platform support this? What's the roadmap?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["UoT", "ToT", "CoT", "CLARA"]},
    {"id": 43, "subject": "VIP: White-label deployment with custom branding", "message": "We want to white-label your entire platform for our franchise network of 200 locations. Each franchise needs: custom branding/logo, their own domain, separate billing, localized content in 8 languages, and custom workflow configurations. We also need a master dashboard to manage all franchises centrally. What's the feasibility, timeline, and pricing for this level of customization?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["ToT", "GST", "CoT", "CLARA"]},
    {"id": 44, "subject": "VIP: SLA breach compensation and contract renegotiation", "message": "This is our 3rd SLA breach in 6 months. Per our Platinum SLA: 99.99% uptime, <15min response time, dedicated CSM. Reality: 99.7% uptime (3 outages), 4+ hour response times, no CSM assigned. Under our contract, each breach entitles us to 5% of quarterly fees as credit, plus the right to renegotiate terms. We're invoking both. We need: 1) $75K in credits for 3 breaches. 2) Meeting with your VP of Customer Success within 48 hours. 3) Written remediation plan. 4) Option to terminate without penalty if 4th breach occurs.", "category": "billing", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["UoT", "Self-Consistency", "Billing Intelligence", "Graceful Escalation"]},
    {"id": 45, "subject": "VIP: Multi-tenant architecture for government compliance", "message": "We're a government contractor and need to deploy your platform in a FedRAMP High environment. Our requirements: 1) FIPS 140-2 encryption at rest and in transit. 2) SOC 2 Type II compliance documentation. 3) Data sovereignty guarantees (all data must remain in US). 4) Separate tenant isolation certification. 5) Audit logging with 7-year retention. 6) Background-checked personnel access. We have a $2M contract at stake. Can your platform meet these requirements?", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["UoT", "ToT", "GST", "CoT", "CLARA"]},

    # 46-50: GST / Least-to-Most (R9: strategic decision, R10: complexity > 0.7)
    {"id": 46, "subject": "Strategic: Merge 3 separate workspaces into one unified instance", "message": "We have 3 separate workspaces (created by 3 different departments) that we need to merge into one. Workspace A: 200K tickets, 50 agents, 200 automations. Workspace B: 80K tickets, 20 agents, 75 automations. Workspace C: 15K tickets, 5 agents, 10 automations. Challenges: overlapping contact records, conflicting automation rules, different custom fields, and varying SLA policies. We need a step-by-step merge strategy that preserves all data and minimizes disruption.", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["GST", "Least-to-Most", "CoT", "CLARA"]},
    {"id": 47, "subject": "Complex: Rebuild automation rules after accidental bulk deletion", "message": "One of our admins accidentally deleted all 150 automation rules in our workspace. We have a backup from 3 months ago but 40 new rules were created since then. We need to: 1) Restore the backup rules. 2) Recreate the 40 missing rules from scratch (we have screenshots of 25 of them). 3) Test all rules in sandbox before going live. 4) Set up rule deletion safeguards to prevent this from happening again. This is urgent — our support workflow is completely manual right now.", "category": "saas_support", "priority": "critical", "channel": "chat", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Least-to-Most", "GST", "CoT", "ReAct"]},
    {"id": 48, "subject": "Strategic: Evaluate migration from Zendesk to your platform", "message": "We're considering migrating from Zendesk to your platform. Current setup: 500K tickets, 100 agents, 250 macros, 75 triggers, 50 automations, 15 custom apps, and integrations with Salesforce, Jira, and Slack. Key questions: 1) Can you import all our historical data? 2) Will our SLA policies transfer? 3) Is there feature parity for our most-used features? 4) What's the migration timeline? 5) What's the total cost for equivalent setup? 6) Is there a migration team to assist?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["GST", "ToT", "CoT", "CLARA"]},
    {"id": 49, "subject": "Complex: Multi-brand, multi-region, multi-language setup", "message": "We operate 5 brands across 12 countries with support in 8 languages. We need: 1) Separate brand identities within one platform instance. 2) Region-specific SLA policies (e.g., Germany: 1hr response, India: 4hr). 3) Language routing based on customer locale. 4) Separate billing per brand. 5) Cross-brand reporting. 6) Unified knowledge base with brand-specific sections. Can your platform handle this complexity? What would the architecture look like?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["Least-to-Most", "GST", "ToT", "CoT"]},
    {"id": 50, "subject": "Strategic: Disaster recovery and business continuity planning", "message": "We need a comprehensive disaster recovery plan for our deployment. Requirements: 1) RPO < 1 hour, RTO < 4 hours. 2) Geographic redundancy across 2 regions. 3) Automated failover. 4) Quarterly DR testing. 5) Documented escalation procedures. 6) Communication plan for stakeholders during outages. We also need to know: What's your platform's DR capability? What guarantees do you provide? How have you handled past major incidents?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["GST", "CoT", "ReAct", "CLARA"]},

    # ─── ENRICHMENT ENGINE TRIGGERS ───

    # 51-55: Emotional Intelligence Engine — high emotion, anger, distress
    {"id": 51, "subject": "I WILL SUE YOUR COMPANY — ABSOLUTELY DISGUSTED", "message": "THIS IS THE WORST COMPANY I HAVE EVER DEALT WITH!!! Your product caught FIRE while charging and nearly burned my house down!!! My 3-year-old was in the next room!!! I am contacting my lawyer, the consumer protection agency, AND posting this on every social media platform. I have photos and videos of the burnt device. You people are selling DANGEROUS products and I will NOT rest until you're held accountable!!!", "category": "complaint", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Emotional Intelligence", "Emergency Detection", "CLARA", "Graceful Escalation", "Loophole Detection"]},
    {"id": 52, "subject": "Crying right now — you ruined my daughter's birthday", "message": "I ordered a custom birthday cake for my daughter's 5th birthday party. I paid $180 for a princess castle cake. What arrived was a SMASHED, UNRECOGNIZABLE mess. The party is in 2 hours and I have NO cake. My daughter has been looking forward to this for weeks and now she's going to be heartbroken. I can't even get a replacement in time. This isn't just a ruined order — you ruined a little girl's birthday.", "category": "delivery", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Emotional Intelligence", "Shipping Intelligence", "CLARA", "Graceful Escalation"]},
    {"id": 53, "subject": "Feel cheated and lied to — your sales team misled us", "message": "Your sales representative explicitly told us the Enterprise plan includes 'unlimited API calls'. Now after signing a 2-year contract for $50K, we're hitting a 100K/day limit and being told 'unlimited' means 'within fair use'. This is DECEPTIVE. Your own marketing page says 'unlimited'. We feel cheated and want either the limit removed or the contract cancelled without penalty. How can you justify this?", "category": "complaint", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Emotional Intelligence", "Loophole Detection", "Billing Intelligence", "CLARA"]},
    {"id": 54, "subject": "Terrified — someone accessed my account from another country", "message": "I just got a login notification from a device in Russia, but I'm in India and I've never been to Russia. Someone has my password! I'm terrified they can see my personal data, payment methods, and order history. I immediately changed my password but I can still see activity I didn't do. PLEASE help me secure my account RIGHT NOW. What data did they access? Do I need to freeze my credit cards?", "category": "account", "priority": "critical", "channel": "chat", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Emotional Intelligence", "Emergency Detection", "Tech Diagnostics"]},
    {"id": 55, "subject": "Devastated — lost 3 years of business data due to your bug", "message": "Your platform's bulk delete feature had a bug and deleted ALL our customer data instead of just the 5 test records I selected. 3 years of customer interactions, purchase history, support tickets — GONE. I'm a small business owner and this data is the lifeblood of my company. Your agent confirmed it was a bug on your end but says data recovery 'may not be possible'. I'm devastated. This could literally bankrupt my business.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Emotional Intelligence", "Emergency Detection", "Tech Diagnostics", "Graceful Escalation", "CLARA"]},

    # 56-58: Churn Retention Engine — cancellation/retention scenarios
    {"id": 56, "subject": "Cancelling — your platform is too slow and unreliable", "message": "I want to cancel my subscription effective immediately. Your platform has been nothing but problems: slow load times, random outages, and terrible support. We've been a customer for 8 months and it's only gotten worse. We're switching to Freshdesk. Please cancel and refund the remaining 4 months of our annual plan. I don't want any retention offers or discounts — I'm done.", "category": "cancellation", "priority": "critical", "channel": "chat", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Churn Retention", "Emotional Intelligence", "Billing Intelligence", "CLARA"]},
    {"id": 57, "subject": "Downgrading to free — can't justify the cost anymore", "message": "We need to downgrade from Growth to the Free plan. Our startup funding fell through and we can't afford $79/month anymore. What features will we lose? Can we keep our data? Is there any discount for startups? We'd love to stay if there's a way to make it affordable.", "category": "billing", "priority": "medium", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Churn Retention", "Billing Intelligence", "CLARA"]},
    {"id": 58, "subject": "Switching to competitor — better features for half the price", "message": "Just wanted to let you know we're not renewing our contract. Your competitor offers the same features for 40% less, plus they have built-in video calling and better analytics. We've been loyal customers for 2 years but you haven't kept up with the market. Cancel at end of billing period and export all our data.", "category": "cancellation", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Churn Retention", "Billing Intelligence", "CLARA"]},

    # 59-62: Billing Intelligence Engine — billing/payment/refund specific
    {"id": 59, "subject": "Proration calculation makes no sense on upgrade", "message": "I upgraded from Starter ($29/month) to Growth ($79/month) on the 15th of a 30-day billing period. Your system charged me the FULL $79 for the new plan plus $29 for the old plan, totaling $108. But the proration credit for the unused 15 days of Starter should be $14.50, making the total $93.50. Instead, I was charged $108 with a proration credit of only $4.83. Your math doesn't add up. Please explain the proration formula you're using.", "category": "billing", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Billing Intelligence", "CoT", "Self-Consistency", "CLARA"]},
    {"id": 60, "subject": "Auto-renewal charged my expired card — how?", "message": "My subscription auto-renewed yesterday for $599 but the credit card on file expired in January! How did you charge an expired card? More importantly, I had set auto-renewal to OFF but your system turned it back on during a platform update (per your own release notes). I never consented to this charge. I want an immediate refund and written confirmation that auto-renewal is disabled.", "category": "billing", "priority": "critical", "channel": "chat", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Billing Intelligence", "Reverse Thinking", "Loophole Detection"]},
    {"id": 61, "subject": "Currency conversion error on international invoice", "message": "Our company is based in the UK and we're being billed in GBP. This month's invoice shows £890 but at the current exchange rate, our $999 USD plan should be approximately £795. The exchange rate you're using seems to be from 3 months ago. We're being overcharged by approximately £95 due to stale FX rates. Can you please use current exchange rates or allow us to pay in USD directly?", "category": "billing", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Billing Intelligence", "CoT", "CLARA"]},
    {"id": 62, "subject": "Credit note from 6 months ago never applied to account", "message": "In October, your team issued a credit note CN-2024-4482 for $350 due to a billing error. It was never applied to our account. We've been overpaying by that amount for 6 months. I need: 1) The credit applied immediately. 2) Interest on the $350 for 6 months (we're a business, that's our working capital). 3) A written explanation of why credit notes aren't automatically applied. This is basic accounting.", "category": "billing", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Billing Intelligence", "Step-Back", "CLARA"]},

    # 63-65: Tech Diagnostics Engine — technical/bug scenarios
    {"id": 63, "subject": "Cron job executing 8 hours early due to timezone bug", "message": "Our scheduled automation (cron: '0 9 * * 1-5' — 9 AM weekdays IST) is executing at 1 AM IST instead. It seems your cron scheduler is treating the timezone as UTC rather than the configured IST. This is causing: 1) Automated emails sent at 1 AM. 2) Reports generated with previous day's data. 3) Workflow triggers firing while our team is asleep. We have 23 automations affected. Please fix the timezone handling in the cron scheduler immediately.", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Tech Diagnostics", "CoT", "ReAct"]},
    {"id": 64, "subject": "Mobile app crashes when uploading images > 5MB", "message": "Your mobile app (v4.2.1 on iOS 17) crashes consistently when attaching images larger than 5MB to tickets. Steps to reproduce: 1) Open a ticket. 2) Tap 'Attach'. 3) Select a photo > 5MB. 4) App crashes to home screen. Works fine with smaller images. This is blocking our field agents from uploading high-res photos of defective products. Android app has the same issue with images > 8MB.", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Tech Diagnostics", "CoT", "CLARA"]},
    {"id": 65, "subject": "API v3 deprecation breaking our integration — 30-day notice not enough", "message": "Your v3 API deprecation notice gave us 30 days to migrate to v4. Our integration has 200+ endpoints, custom authentication middleware, and 47 test suites. A proper migration takes 3-4 months minimum. Industry standard is 12-18 months deprecation notice. We need: 1) v3 lifetime extended by at least 6 months. 2) A detailed migration guide. 3) A compatibility shim. 4) A dedicated engineer for migration support. This is unreasonable and will break our production system.", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Tech Diagnostics", "CoT", "ReAct", "Graceful Escalation"]},

    # 66-68: Shipping Intelligence Engine — shipping/delivery/tracking
    {"id": 66, "subject": "Perishable food shipment stuck in warehouse for 4 days", "message": "Order #EC-5567 contains perishable food items (fresh produce and dairy) that has been sitting in your Mumbai warehouse for 4 days with no movement. The delivery window was 24 hours. These items will be completely spoiled by the time they arrive. I need you to: 1) Locate the package immediately. 2) If still viable, expedite with cold chain logistics. 3) If spoiled, issue full refund + compensation for the inconvenience. This is a health hazard — spoiled food cannot be delivered.", "category": "logistics", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Shipping Intelligence", "Emergency Detection", "Emotional Intelligence", "CLARA"]},
    {"id": 67, "subject": "3 separate deliveries for 1 order — all delayed differently", "message": "My single order #EC-3390 was split into 3 shipments. Package A: delivered on time. Package B: 5 days late, arrived damaged. Package C: still not delivered, no tracking update for 8 days. Why was my order split? Why are the tracking numbers not linked? I need: 1) Status of Package C. 2) Replacement for damaged items in Package B. 3) Shipping fee refund for the entire order since it wasn't delivered as promised.", "category": "logistics", "priority": "high", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Shipping Intelligence", "CoT", "CLARA"]},
    {"id": 68, "subject": "International shipment held by customs — need documents ASAP", "message": "My shipment to Japan is held at Narita customs. They require: 1) Commercial invoice with HS codes. 2) Certificate of origin. 3) Packing list. 4) Import declaration form. Your shipping label only included a basic invoice without HS codes. The Japanese customs office has given us 5 business days to provide documentation or the shipment will be returned. This is a $3,000 order. Please provide all required documents immediately.", "category": "logistics", "priority": "critical", "channel": "email", "industry": "logistics", "customer_tier": "pro", "expected_frameworks": ["Shipping Intelligence", "ReAct", "CLARA"]},

    # ─── GRACEFUL ESCALATION FRAMEWORK ───

    # 69-72: Escalation triggers — VIP, emergency, legal, media threats
    {"id": 69, "subject": "Taking this to social media and consumer court", "message": "I've been trying to resolve my issue for 3 weeks with no success. I'm now going to: 1) Post about this on Twitter (45K followers). 2) File a complaint with the National Consumer Helpline. 3) Write a detailed review on Trustpilot and G2. 4) Contact a consumer affairs journalist. Your support team keeps giving me the same scripted responses. I need to speak to someone with ACTUAL authority to resolve this. Give me a manager or director — NOW.", "category": "complaint", "priority": "critical", "channel": "chat", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Graceful Escalation", "Emotional Intelligence", "CLARA"]},
    {"id": 70, "subject": "Legal action — your terms of service are unenforceable", "message": "I've had my legal team review your Terms of Service. Several clauses violate consumer protection laws in our jurisdiction: 1) The mandatory arbitration clause is not enforceable under Indian Consumer Protection Act 2019. 2) The limitation of liability clause exceeds statutory caps. 3) The auto-renewal without notice violates RBI guidelines. We intend to challenge these in court unless you resolve our dispute within 14 days. Consider this formal notice.", "category": "complaint", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Graceful Escalation", "Loophole Detection", "CLARA", "Reverse Thinking"]},
    {"id": 71, "subject": "Patient safety issue with your medical device tracking system", "message": "Your tracking system for medical device shipments is showing incorrect delivery status. Our hospital has 3 patients waiting for critical implant deliveries that your system says are 'delivered' but haven't arrived. These are scheduled surgeries — delays put patients at risk. We need immediate manual verification of all 3 shipment locations. This is a patient safety issue that requires urgent executive attention.", "category": "logistics", "priority": "critical", "channel": "voice", "industry": "logistics", "customer_tier": "vip", "expected_frameworks": ["Graceful Escalation", "Emergency Detection", "Shipping Intelligence", "CLARA"]},
    {"id": 72, "subject": "Escalation: Your agent hung up on me after 45 minute wait", "message": "I waited on hold for 45 minutes and when I finally got an agent, they hung up on me mid-sentence when I asked for a supervisor. I called back and was told the wait time is 'over 60 minutes'. This is the worst customer service I've ever experienced. I need: 1) An immediate callback from a supervisor. 2) A written apology. 3) Action taken against the agent who hung up. 4) Resolution of my original issue (refund of $349 for defective product).", "category": "complaint", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Graceful Escalation", "Emotional Intelligence", "CLARA"]},

    # ─── LOOPHOLE DETECTION ENGINE ───

    # 73-76: Loophole exploitation attempts
    {"id": 73, "subject": "Exploiting your 'no questions asked' return policy for used items", "message": "I've bought and returned 12 items in the past month under your 'no questions asked' 30-day return policy. I use each item for 29 days and then return it for a full refund. Your policy doesn't say anything about a return limit or condition requirements. I'd like to return my latest purchase too — a $599 tablet that I've used for 28 days. Please send the return label.", "category": "returns", "priority": "medium", "channel": "chat", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Loophole Detection", "CLARA", "GSD"]},
    {"id": 74, "subject": "Price manipulation between two regional stores", "message": "Your Indian store sells the same product for ₹15,000 while the US store sells it for $120 (approximately ₹9,960). I want to buy from the US store and have it shipped to India. Your terms say 'products can be shipped internationally' but your pricing team might not have intended such a large price gap. Can I place the order at the US price?", "category": "general", "priority": "medium", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Loophole Detection", "CLARA", "Billing Intelligence"]},
    {"id": 75, "subject": "Using free trial repeatedly with different emails", "message": "I've signed up for your 14-day free trial 6 times using different email addresses from my domain aliases (user+1@domain.com, user+2@domain.com, etc.). I think your system should probably prevent this but since it doesn't, I'd like to extend my current trial again. Also, can you tell me when the trial data from my previous accounts gets deleted?", "category": "account", "priority": "low", "channel": "chat", "industry": "saas", "customer_tier": "free", "expected_frameworks": ["Loophole Detection", "CLARA", "GSD"]},
    {"id": 76, "subject": "Promo code stacking exploit — can I use 5 codes on one order?", "message": "I found 5 different promo codes online: WELCOME10, SUMMER20, REFER15, NEWSLETTER25, and LOYALTY30. Can I apply all of them to a single $500 order? That would bring it down to $500 - 10% - 20% - 15% - 25% - 30% = $180. Your checkout page doesn't seem to limit the number of promo codes. If this works, I'd like to proceed with the purchase.", "category": "general", "priority": "medium", "channel": "chat", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Loophole Detection", "Billing Intelligence", "CLARA"]},

    # ─── SMS CHANNEL SPECIFIC ───

    # 77-80: SMS-specific short messages
    {"id": 77, "subject": "Order status SMS", "message": "Hi, order #EC-2234 kab tak deliver hoga? 5 din ho gaye.", "category": "order_tracking", "priority": "medium", "channel": "sms", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["GSD", "CLARA", "CRP", "Shipping Intelligence"]},
    {"id": 78, "subject": "Payment failed SMS", "message": "My payment of Rs 2499 failed but money deducted from UPI. Order #EC-5567. Refund kab milega?", "category": "billing", "priority": "high", "channel": "sms", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Billing Intelligence", "CLARA", "GSD"]},
    {"id": 79, "subject": "Flight cancellation refund SMS", "message": "My flight SG-812 got cancelled. Booked through your app. Full refund needed ASAP. PNR: ABC123", "category": "refunds", "priority": "critical", "channel": "sms", "industry": "logistics", "customer_tier": "free", "expected_frameworks": ["CLARA", "CRP", "GSD", "Billing Intelligence"]},
    {"id": 80, "subject": "Appointment reschedule SMS", "message": "Need to reschedule my delivery slot from 2-4pm to 6-8pm tomorrow. Order #LG-7789. Is it possible?", "category": "address_change", "priority": "low", "channel": "sms", "industry": "logistics", "customer_tier": "free", "expected_frameworks": ["GSD", "CLARA", "Shipping Intelligence"]},

    # ─── VOICE/CALL CHANNEL SPECIFIC ───

    # 81-84: Voice call — conversational, real-time, high urgency
    {"id": 81, "subject": "Emergency: Prescription medication delivery delayed 2 weeks", "message": "[TRANSCRIPT] Caller is extremely anxious. Has been waiting for prescription medication for 2 weeks. The medication is for a chronic condition and missing doses has caused health deterioration. Caller has contacted the pharmacy who says the shipment hasn't arrived from the supplier. Urgent medical need — needs immediate escalation to find the package and arrange emergency delivery.", "category": "logistics", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Emergency Detection", "Emotional Intelligence", "Graceful Escalation", "Shipping Intelligence"]},
    {"id": 82, "subject": "Fraudulent charge on elderly parent's account", "message": "[TRANSCRIPT] Elderly customer's daughter calling. Found $2,400 in unauthorized charges on father's account over 3 months. Father has dementia and didn't realize. Charges include premium subscriptions, in-app purchases, and international shipping fees. Needs: 1) Immediate account freeze. 2) Fraud investigation. 3) Full refund of unauthorized charges. 4) Account security review. Very emotional caller — needs compassionate handling.", "category": "billing", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "free", "expected_frameworks": ["Emotional Intelligence", "Billing Intelligence", "Emergency Detection", "Graceful Escalation"]},
    {"id": 83, "subject": "Restaurant owner — delivery platform crashing during dinner rush", "message": "[TRANSCRIPT] Restaurant owner calling during peak dinner rush (7:30 PM). Your delivery platform is down and they can't receive or process any orders. This is their busiest time — they estimate losing $2,000/hour in revenue. The crash started 30 minutes ago. They need: 1) Immediate technical fix. 2) Compensation for lost revenue. 3) Assurance this won't recur. Very stressed caller — their staff is standing idle.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Emergency Detection", "Graceful Escalation", "Emotional Intelligence", "Tech Diagnostics"]},
    {"id": 84, "subject": "Live TV appearance tomorrow — product not arrived", "message": "[TRANSCRIPT] Customer has a live TV appearance tomorrow morning to demonstrate your product. Ordered 2 weeks ago with guaranteed 3-day delivery. Product hasn't arrived. This is a major brand partnership opportunity. If the product doesn't arrive by 8 AM tomorrow, the TV appearance falls through. Caller needs: 1) Immediate location of package. 2) Personal delivery tonight if possible. 3) Backup plan if delivery can't happen.", "category": "logistics", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "pro", "expected_frameworks": ["Graceful Escalation", "Shipping Intelligence", "Emotional Intelligence", "Emergency Detection"]},

    # ─── SOCIAL MEDIA CHANNEL ───

    # 85-87: Social media — public-facing, brand reputation
    {"id": 85, "subject": "Twitter complaint: Worst customer service ever", "message": "@YourCompany I've been waiting 2 weeks for my refund. Your support team keeps closing my tickets without resolution. This is the 5th time I'm reaching out. #WorstSupport #Scam #NeverAgain. Order #EC-6678. $349 refund pending since last month. Your CEO needs to know how terrible your support is.", "category": "complaint", "priority": "critical", "channel": "social", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Emotional Intelligence", "Graceful Escalation", "CLARA", "CRP"]},
    {"id": 86, "subject": "LinkedIn post: Data breach at your company", "message": "Concerning reports from multiple users about seeing other companies' data in their dashboards. If true, this is a serious data breach. As a cybersecurity professional, I'm advising my clients to suspend their accounts until you provide a transparent incident report. #DataSecurity #Breach #Compliance. We need an immediate public statement from your security team.", "category": "saas_support", "priority": "critical", "channel": "social", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Graceful Escalation", "Emergency Detection", "CLARA"]},
    {"id": 87, "subject": "Instagram story: Product caused allergic reaction", "message": "Your organic face cream gave me a severe allergic reaction! My face is swollen and I had to go to the ER. The ingredient list on your website doesn't match what's on the actual product. This is a safety violation! I'm sharing my story with my 50K followers. #ProductSafety #AllergicReaction #ConsumerRights", "category": "complaint", "priority": "critical", "channel": "social", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Emergency Detection", "Emotional Intelligence", "Graceful Escalation", "Loophole Detection", "CLARA"]},

    # ─── MULTI-STEP COMPLEX SCENARIOS ───

    # 88-92: Multi-step resolution requiring framework combinations
    {"id": 88, "subject": "Full migration: 3 systems → 1 platform, with zero data loss", "message": "We're consolidating from 3 separate systems (Zendesk for support, Salesforce for CRM, Intercom for chat) into your single platform. Current data: 1M tickets, 500K contacts, 200K chat transcripts, 50K articles. Timeline: 6 weeks. Constraints: Zero data loss, minimal disruption, preserve all relationships between records. Need: Step-by-step migration plan, data mapping templates, testing checklist, rollback strategy, and a dedicated migration specialist.", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["Least-to-Most", "GST", "ToT", "CoT", "ReAct"]},
    {"id": 89, "subject": "Regulatory compliance audit — need everything documented", "message": "We're undergoing a SOC 2 Type II audit next month. We need from your platform: 1) Complete access logs for all our users (6 months). 2) Data processing agreements. 3) Sub-processor list with certifications. 4) Encryption documentation (at-rest and in-transit). 5) Incident response procedures. 6) Business continuity plan. 7) Vulnerability scan reports. 8) Change management logs. Our auditor requires all documentation within 2 weeks. Can you provide this?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "ReAct", "CLARA", "GST"]},
    {"id": 90, "subject": "Multi-department workflow setup with approval chains", "message": "We need to set up a complex multi-department workflow: Customer complaint → Tier 1 Support (auto-classify) → If billing: Route to Finance (with manager approval for >$500 refunds) → If technical: Route to Engineering (with severity classification) → If VIP: Route to CSM (with director notification) → All resolved tickets: Auto-survey + knowledge base update. We have 6 departments, 12 approval rules, and 3 escalation paths. Can you help us architect this?", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["GST", "ToT", "CoT", "CLARA"]},
    {"id": 91, "subject": "Quarterly business review — need comprehensive analytics", "message": "Preparing our QBR with your platform. Need: 1) Ticket volume trends (by channel, category, priority). 2) Resolution time analysis (first response, full resolution). 3) Agent performance metrics (utilization, CSAT, resolution rate). 4) Customer satisfaction trends. 5) SLA compliance rate. 6) Cost per ticket analysis. 7) Automation efficiency metrics. 8) Comparison vs last quarter. Can your analytics module generate all of this, or do I need to export raw data?", "category": "saas_support", "priority": "medium", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "CLARA", "CRP"]},
    {"id": 92, "subject": "Custom integration: Connect your API to our ERP system", "message": "We need to build a real-time bidirectional sync between your platform and SAP S/4HANA. Required data flows: 1) Tickets → SAP Service Orders (create, update, close). 2) SAP Customer Master → Your Contacts (sync, deduplicate). 3) SAP Billing → Your Invoices (validate, reconcile). 4) Your Knowledge Base → SAP Knowledge Articles. 5) Your Analytics → SAP Dashboard. Constraints: OAuth2 authentication, retry logic, idempotency, and audit trail for all sync operations.", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["ReAct", "CoT", "Least-to-Most", "CLARA"]},

    # ─── EDGE CASES & NICHE SCENARIOS ───

    # 93-95: Accessibility, legal, privacy edge cases
    {"id": 93, "subject": "ADA compliance — screen reader support broken", "message": "Our organization serves visually impaired users and your platform's latest update broke screen reader compatibility. Key issues: 1) ARIA labels missing on ticket list. 2) Keyboard navigation broken in the reply editor. 3) Color contrast fails WCAG 2.1 AA standards on the dashboard. 4) Focus management is erratic after modal close. This is an ADA compliance issue — we could both face legal liability. We need a hotfix within 48 hours or we need to disable the update.", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "Graceful Escalation", "Tech Diagnostics", "CLARA"]},
    {"id": 94, "subject": "GDPR right to erasure — need all data permanently deleted", "message": "We're exercising our right to erasure under GDPR Article 17. We need ALL of our data permanently deleted from your systems including: 1) All tickets and messages. 2) All customer records. 3) All analytics data. 4) All backups (you must confirm backup deletion). 5) All third-party processor data. 6) All log entries containing PII. You have 30 days to comply. We also need a Certificate of Destruction confirming all data has been irrecoverably deleted.", "category": "saas_support", "priority": "high", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "CLARA", "Graceful Escalation"]},
    {"id": 95, "subject": "Subpoena for customer communication records", "message": "We've received a subpoena requesting all communication records between our company and a specific customer for the past 2 years. We need your help: 1) Export all tickets, messages, and notes for customer ID CUST-7782. 2) Include metadata (timestamps, agent IDs, channel). 3) Provide in a format acceptable for legal proceedings. 4) Confirm chain of custody / data integrity. 5) Advise on any data retention policies that may affect completeness. This is time-sensitive — response required within 10 business days.", "category": "saas_support", "priority": "critical", "channel": "email", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["CoT", "ReAct", "Graceful Escalation", "CLARA"]},

    # 96-98: Cross-industry scenarios (logistics, healthcare-adjacent, education)
    {"id": 96, "subject": "Cold chain logistics — temperature-sensitive vaccine shipment", "message": "We're a pharmaceutical distributor and your platform handles our customer support. A customer reported that their vaccine shipment (requires -20°C storage) arrived at +8°C — the cold chain was broken. This affects 500 doses worth $75,000. The customer needs: 1) Immediate replacement shipment with verified cold chain. 2) Documentation for regulatory reporting. 3) Investigation of where the cold chain broke. 4) Preventive measures to avoid recurrence. This is a patient safety and regulatory issue.", "category": "logistics", "priority": "critical", "channel": "voice", "industry": "logistics", "customer_tier": "vip", "expected_frameworks": ["Emergency Detection", "Shipping Intelligence", "Graceful Escalation", "CoT", "ReAct", "CLARA"]},
    {"id": 97, "subject": "Education platform — student data accidentally shared with wrong school", "message": "Our education platform (running on your infrastructure) accidentally shared 2,000 student records with the wrong school district. This includes: names, grades, disciplinary records, and IEP information. This is a FERPA violation. We need: 1) Immediate data recall/deletion from the receiving district. 2) Audit of data access logs. 3) Notification templates for affected families. 4) Incident report for FERPA compliance office. 5) Technical fix to prevent future cross-district data leaks.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "saas", "customer_tier": "vip", "expected_frameworks": ["Emergency Detection", "Graceful Escalation", "Tech Diagnostics", "CoT", "CLARA"]},
    {"id": 98, "subject": "E-commerce flash sale — site can't handle the traffic", "message": "We're running a Diwali flash sale (our biggest event of the year) and your platform is buckling under the load. Customer support queue has gone from 50 to 2,000 tickets in 30 minutes. Response times are 4+ hours instead of 2 minutes. Customers are furious and posting complaints on social media. We need: 1) Emergency capacity increase. 2) Priority queue for angry customers. 3) Auto-responses for common questions. 4) Extra agent seats unlocked. We're losing $50K/hour in abandoned carts.", "category": "saas_support", "priority": "critical", "channel": "voice", "industry": "ecommerce", "customer_tier": "pro", "expected_frameworks": ["Emergency Detection", "Graceful Escalation", "CLARA", "Emotional Intelligence"]},

    # 99-100: Reflexion triggers (R11: response rejected) — customer rejects AI response
    {"id": 99, "subject": "Your AI response was completely wrong — REJECTED", "message": "The AI agent that responded to my ticket (#T-99234) gave me completely incorrect information. It told me to 'clear my browser cache' for what is clearly a server-side 500 error. I'm a senior developer and I know the difference between a client-side and server-side issue. The AI wasted 30 minutes of my time with generic troubleshooting. I need a HUMAN agent who understands backend engineering. Don't give me another AI response.", "category": "saas_support", "priority": "high", "channel": "chat", "industry": "saas", "customer_tier": "pro", "expected_frameworks": ["Reflexion", "CoT", "Tech Diagnostics", "CLARA"]},
    {"id": 100, "subject": "AI response was insensitive about my medical condition", "message": "Your AI agent responded to my ticket about a delayed medical device delivery with 'We apologize for the inconvenience. Here's a 10% discount code for your next purchase.' I don't want a discount — I need my CPAP machine that I need to BREATHE while sleeping. The AI completely missed the urgency and medical context. This is not just an 'inconvenience' — it's a health emergency. I need an empathetic human response, not a robotic template.", "category": "complaint", "priority": "critical", "channel": "email", "industry": "ecommerce", "customer_tier": "free", "expected_frameworks": ["Reflexion", "Emotional Intelligence", "Emergency Detection", "CLARA", "Graceful Escalation"]},
]


# ══════════════════════════════════════════════════════════════════
# TEST RUNNER
# ══════════════════════════════════════════════════════════════════

COMPANY_ID = str(uuid.uuid4())
VARIANT_TIERS = ["mini_parwa", "parwa", "parwa_high"]
TIER_LABELS = {
    "mini_parwa": "PARWA Starter (10 nodes, Tier 1)",
    "parwa": "PARWA Growth (22 nodes, Tier 1+2)",
    "parwa_high": "PARWA High (27 nodes, ALL tiers)",
}

# Track results across all tiers
all_results: Dict[str, List[Dict]] = {}
framework_coverage: Dict[str, set] = {}


async def process_ticket_through_pipeline(
    ticket: Dict[str, Any],
    variant_tier: str,
) -> Dict[str, Any]:
    """Send a single ticket through the variant pipeline bridge."""

    from app.core.variant_pipeline_bridge import process_customer_care_message

    session_context = {
        "variant_tier": variant_tier,
        "industry": ticket.get("industry", "general"),
        "company_id": COMPANY_ID,
    }

    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            process_customer_care_message(
                query=ticket["message"],
                company_id=COMPANY_ID,
                session_context=session_context,
                conversation_id=f"test-{ticket['id']}-{variant_tier}",
                ticket_id=f"ticket-{ticket['id']}",
                channel=ticket.get("channel", "chat"),
                customer_id=f"customer-{ticket['id']}",
                customer_tier=ticket.get("customer_tier", "free"),
            ),
            timeout=30,  # 30 second per-ticket timeout
        )

        latency_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "ticket_id": ticket["id"],
            "subject": ticket["subject"],
            "variant_tier": result.variant_tier,
            "industry": result.industry,
            "pipeline_status": result.pipeline_status,
            "quality_score": result.quality_score,
            "latency_ms": latency_ms,
            "billing_tokens": result.billing_tokens,
            "steps_completed": result.steps_completed,
            "technique_used": result.technique_used if isinstance(result.technique_used, str) else str(result.technique_used),
            "technique_detail": result.technique_used if isinstance(result.technique_used, dict) else {},
            "emergency_flag": result.emergency_flag,
            "empathy_score": result.empathy_score,
            "classification_intent": result.classification_intent,
            "channel": ticket.get("channel", "chat"),
            "customer_tier": ticket.get("customer_tier", "free"),
            "expected_frameworks": ticket.get("expected_frameworks", []),
            "response_preview": result.response_text[:200] if result.response_text else "",
            "error": None,
        }

    except asyncio.TimeoutError:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "ticket_id": ticket["id"],
            "subject": ticket["subject"],
            "variant_tier": variant_tier,
            "industry": ticket.get("industry", "general"),
            "pipeline_status": "timeout",
            "quality_score": 0.0,
            "latency_ms": latency_ms,
            "billing_tokens": 0,
            "steps_completed": [],
            "technique_used": "",
            "emergency_flag": False,
            "empathy_score": 0.0,
            "classification_intent": "",
            "channel": ticket.get("channel", "chat"),
            "customer_tier": ticket.get("customer_tier", "free"),
            "expected_frameworks": ticket.get("expected_frameworks", []),
            "response_preview": "",
            "error": "Pipeline timeout after 30s",
        }
    except Exception as e:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "ticket_id": ticket["id"],
            "subject": ticket["subject"],
            "variant_tier": variant_tier,
            "industry": ticket.get("industry", "general"),
            "pipeline_status": "error",
            "quality_score": 0.0,
            "latency_ms": latency_ms,
            "billing_tokens": 0,
            "steps_completed": [],
            "technique_used": "",
            "emergency_flag": False,
            "empathy_score": 0.0,
            "classification_intent": "",
            "channel": ticket.get("channel", "chat"),
            "customer_tier": ticket.get("customer_tier", "free"),
            "expected_frameworks": ticket.get("expected_frameworks", []),
            "response_preview": "",
            "error": str(e),
        }


def print_tier_summary(tier: str, results: List[Dict]) -> None:
    """Print a summary for one variant tier."""

    label = TIER_LABELS.get(tier, tier)
    print(f"\n{'='*80}")
    print(f"  RESULTS: {label}")
    print(f"{'='*80}")

    total = len(results)
    completed = [r for r in results if r["pipeline_status"] == "completed"]
    errors = [r for r in results if r["pipeline_status"] == "error"]
    avg_quality = sum(r["quality_score"] for r in completed) / len(completed) if completed else 0
    avg_latency = sum(r["latency_ms"] for r in completed) / len(completed) if completed else 0
    total_tokens = sum(r["billing_tokens"] for r in completed)

    print(f"  Total tickets:    {total}")
    print(f"  Completed:        {len(completed)}")
    print(f"  Errors:           {len(errors)}")
    print(f"  Avg Quality:      {avg_quality:.1f}")
    print(f"  Avg Latency:      {avg_latency:.0f}ms")
    print(f"  Total Tokens:     {total_tokens}")

    # Framework/technique coverage
    techniques_used = set()
    for r in completed:
        if r["technique_used"]:
            techniques_used.add(r["technique_used"])
        for step in r.get("steps_completed", []):
            techniques_used.add(step)

    print(f"\n  Techniques/Steps Activated:")
    for t in sorted(techniques_used):
        print(f"    - {t}")

    # Channel breakdown
    channels = {}
    for r in completed:
        ch = r.get("channel", "chat")
        channels[ch] = channels.get(ch, 0) + 1
    print(f"\n  Channel Breakdown:")
    for ch, cnt in sorted(channels.items()):
        print(f"    - {ch}: {cnt} tickets")

    # Emergency flags
    emergencies = [r for r in completed if r["emergency_flag"]]
    if emergencies:
        print(f"\n  Emergency Flags:  {len(emergencies)} tickets triggered emergency detection")
        for r in emergencies:
            print(f"    - Ticket #{r['ticket_id']}: {r['subject'][:60]}")

    # Errors detail
    if errors:
        print(f"\n  Error Details:")
        for r in errors:
            print(f"    - Ticket #{r['ticket_id']}: {r['error'][:100]}")

    # Top 5 quality and bottom 5
    if completed:
        by_quality = sorted(completed, key=lambda x: x["quality_score"], reverse=True)
        print(f"\n  Top 5 Quality Scores:")
        for r in by_quality[:5]:
            print(f"    - Ticket #{r['ticket_id']}: Q={r['quality_score']:.1f} | {r['technique_used']} | {r['subject'][:50]}")
        print(f"\n  Bottom 5 Quality Scores:")
        for r in by_quality[-5:]:
            print(f"    - Ticket #{r['ticket_id']}: Q={r['quality_score']:.1f} | {r['technique_used']} | {r['subject'][:50]}")


def print_framework_coverage_report() -> None:
    """Print overall framework coverage across all tiers."""

    ALL_FRAMEWORKS = [
        # Tier 1
        "CLARA", "CRP", "GSD", "Smart Router", "Technique Router", "Confidence Scoring",
        # Tier 2
        "CoT", "Reverse Thinking", "ReAct", "Step-Back", "ThoT",
        # Tier 3
        "GST", "UoT", "ToT", "Self-Consistency", "Reflexion", "Least-to-Most",
        # Enrichment Engines
        "Emotional Intelligence", "Churn Retention", "Billing Intelligence",
        "Tech Diagnostics", "Shipping Intelligence",
        # Supporting
        "TRIVYA", "Graceful Escalation", "Loophole Detection",
        "Emergency Detection", "DSPy",
    ]

    print(f"\n{'='*80}")
    print(f"  FRAMEWORK COVERAGE REPORT (across all variant tiers)")
    print(f"{'='*80}")

    for fw in ALL_FRAMEWORKS:
        tiers_hit = []
        for tier, fws in framework_coverage.items():
            if any(fw.lower() in f.lower() for f in fws):
                tiers_hit.append(tier)
        status = "✅" if tiers_hit else "❌"
        tier_str = ", ".join(tiers_hit) if tiers_hit else "NOT TRIGGERED"
        print(f"  {status} {fw:30s} → {tier_str}")

    total_hit = sum(1 for fw in ALL_FRAMEWORKS
                    if any(fw.lower() in f.lower() for fws in framework_coverage.values() for f in fws))
    print(f"\n  Coverage: {total_hit}/{len(ALL_FRAMEWORKS)} frameworks triggered ({total_hit/len(ALL_FRAMEWORKS)*100:.0f}%)")


def save_results_json(results: Dict[str, List[Dict]], filepath: str) -> None:
    """Save results to JSON for later analysis."""

    output = {
        "test_run": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company_id": COMPANY_ID,
            "total_tickets": len(TICKETS),
            "variant_tiers_tested": VARIANT_TIERS,
        },
        "results": {},
    }

    for tier, tier_results in results.items():
        output["results"][tier] = {
            "summary": {
                "total": len(tier_results),
                "completed": len([r for r in tier_results if r["pipeline_status"] == "completed"]),
                "errors": len([r for r in tier_results if r["pipeline_status"] == "error"]),
                "avg_quality": sum(r["quality_score"] for r in tier_results if r["pipeline_status"] == "completed") / max(1, len([r for r in tier_results if r["pipeline_status"] == "completed"])),
                "avg_latency_ms": sum(r["latency_ms"] for r in tier_results if r["pipeline_status"] == "completed") / max(1, len([r for r in tier_results if r["pipeline_status"] == "completed"])),
            },
            "tickets": tier_results,
        }

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to: {filepath}")


async def run_all_tests() -> None:
    """Run all 100 tickets through all 3 variant tiers."""

    print(f"\n{'#'*80}")
    print(f"#  PARWA VARIANT PIPELINE — FULL MANUAL TEST")
    print(f"#  100 Tickets × 3 Variants = 300 Total Tests")
    print(f"#  Company ID: {COMPANY_ID}")
    print(f"#  Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'#'*80}")

    for tier in VARIANT_TIERS:
        label = TIER_LABELS.get(tier, tier)
        print(f"\n{'─'*80}")
        print(f"  Testing: {label}")
        print(f"{'─'*80}")

        tier_results = []
        framework_coverage[tier] = set()

        for i, ticket in enumerate(TICKETS):
            ticket_num = i + 1
            print(f"  [{ticket_num:3d}/100] Ticket #{ticket['id']:3d} | "
                  f"{ticket.get('channel','chat'):7s} | "
                  f"{ticket.get('customer_tier','free'):4s} | "
                  f"{ticket['subject'][:55]:55s} ", end="")

            result = await process_ticket_through_pipeline(ticket, tier)
            tier_results.append(result)

            # Track frameworks
            if result["technique_used"]:
                framework_coverage[tier].add(result["technique_used"])
            for step in result.get("steps_completed", []):
                framework_coverage[tier].add(step)

            # Print status
            status = result["pipeline_status"]
            q = result["quality_score"]
            t = result["technique_used"][:20] if result["technique_used"] else "—"
            print(f"→ {status:10s} | Q={q:5.1f} | {t}")

        all_results[tier] = tier_results
        print_tier_summary(tier, tier_results)

    # Framework coverage report
    print_framework_coverage_report()

    # Save results
    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_results_variant_100.json")
    save_results_json(all_results, results_path)

    print(f"\n{'#'*80}")
    print(f"#  TEST COMPLETE")
    print(f"#  100 tickets × 3 variants = 300 total pipeline runs")
    print(f"{'#'*80}\n")


def main() -> None:
    """Entry point."""

    print(f"\n{'='*80}")
    print(f"  PARWA Variant Pipeline — 100-Ticket Manual Test")
    print(f"  Testing ALL 30 Frameworks Across ALL 3 Variant Tiers")
    print(f"{'='*80}")
    print(f"\n  Frameworks to verify:")
    print(f"    Tier 1: CLARA, CRP, GSD, Smart Router, Technique Router, Confidence")
    print(f"    Tier 2: CoT, Reverse Thinking, ReAct, Step-Back, ThoT")
    print(f"    Tier 3: GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most")
    print(f"    Engines: Emotional Intelligence, Churn Retention, Billing,")
    print(f"            Tech Diagnostics, Shipping Intelligence")
    print(f"    Support: TRIVYA, Graceful Escalation, Loophole Detection,")
    print(f"            Emergency Detection, DSPy")
    print(f"\n  Channels: chat, email, sms, voice, social")
    print(f"  Industries: ecommerce, saas, logistics, general")
    print(f"  Customer Tiers: free, pro, vip")
    print(f"\n  Starting in 3 seconds...")
    time.sleep(3)

    asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
