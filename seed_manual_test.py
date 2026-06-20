"""
PARWA Manual Testing Seed Script — REAL Customer Care Tickets

Creates a SaaS company (TechNova Solutions) with 3 variant instances, 20 customers,
and 100 fake customer care tickets that represent REAL client/customer issues:
- Returns & Refunds
- Order Tracking & Details
- Address Changes
- Logistics & Shipping
- Subscription & Billing (via Paddle)
- Product Cancellation
- Account Management
- Delivery Issues

Uses raw SQL with SQLite-compatible types.
"""

import os
import sys
import uuid
import random
import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "/home/z/my-project/db/parwa_manual_test.db"

# ── REAL Customer Care Ticket Data ──
# These are tickets from CUSTOMERS/CLIENTS of TechNova Solutions,
# NOT tickets about the PARWA product itself.

TICKET_DATA = [
    # ─── Returns & Refunds ───
    {"subject": "Request return for damaged product received", "category": "returns", "priority": "high",
     "messages": ["I received a damaged laptop stand, the hinge is broken and it won't stay upright", "The product arrived with visible cracks on the base, I need a return label immediately", "Package was crushed on arrival, the item inside is completely unusable"]},
    {"subject": "Refund not processed after 14 days", "category": "refunds", "priority": "critical",
     "messages": ["I returned my order 2 weeks ago but still haven't received my refund of $249.99", "Tracking shows the return was delivered but my money hasn't been credited back", "Customer service said 5-7 business days, it's been 14 days now with no refund"]},
    {"subject": "Wrong item shipped, need exchange", "category": "returns", "priority": "high",
     "messages": ["I ordered the blue wireless headphones but received the red ones instead", "The product box says S/M but I ordered L/XL size, need an exchange ASAP", "Got a completely different model than what I ordered, this is very frustrating"]},
    {"subject": "Partial refund for missing accessories", "category": "refunds", "priority": "medium",
     "messages": ["My order was missing the charging cable and carry case that were listed as included", "Only received the main unit but the product page clearly shows 3 accessories", "Need a partial refund of $35 for the missing USB-C cable and adapter"]},
    {"subject": "Return window expired but product defective", "category": "returns", "priority": "high",
     "messages": ["The return period ended 3 days ago but the screen started flickering yesterday", "Product stopped working just after the 30-day return window, this seems like a known defect", "I need an exception for the return window, the item was defective from day one"]},
    {"subject": "Refund amount incorrect - missing tax", "category": "refunds", "priority": "medium",
     "messages": ["My refund was $219.99 but I paid $241.99 including tax, where's the rest?", "The refund doesn't include the sales tax I was charged, please fix this", "Only got the product price back, not the shipping and tax I also paid"]},
    {"subject": "Need to return gift received from someone", "category": "returns", "priority": "low",
     "messages": ["I received this as a gift but already have one, can I return it for store credit?", "Don't have the order number since it was a gift, how do I process a return?", "Can I exchange this gift item for a different color without the receipt?"],
     "channel_hint": "chat"},

    # ─── Order Tracking & Details ───
    {"subject": "Order not received after 10 business days", "category": "order_tracking", "priority": "high",
     "messages": ["Order #TN-4521 was supposed to arrive last week, still no delivery", "Tracking number shows 'label created' but no movement for 7 days", "Paid for express shipping but it's been 10 days with no update"]},
    {"subject": "Tracking shows delivered but I never received it", "category": "order_tracking", "priority": "critical",
     "messages": ["Tracking says delivered yesterday but nothing was at my door, checked with neighbors too", "The delivery photo shows a completely different house, not mine", "Was home all day, no one knocked or left a package, need immediate investigation"]},
    {"subject": "Need to add items to existing order", "category": "order_details", "priority": "medium",
     "messages": ["Just placed order #TN-7832, can I add another item before it ships?", "Forgot to add the warranty to my order, can it be added now?", "Need to change the order to include the accessory bundle before dispatch"]},
    {"subject": "Order confirmation email not received", "category": "order_details", "priority": "low",
     "messages": ["Placed an order 2 hours ago but never got the confirmation email", "Money was deducted from my account but I have no order confirmation", "Checked spam folder too, need proof of my purchase for my records"]},
    {"subject": "Duplicate order placed by mistake", "category": "order_details", "priority": "medium",
     "messages": ["Accidentally clicked submit twice and now have two identical orders", "Browser froze and I refreshed, now I see two charges for the same item", "Need to cancel one of the duplicate orders immediately before it ships"]},

    # ─── Address Changes ───
    {"subject": "Need to change delivery address before shipping", "category": "address_change", "priority": "high",
     "messages": ["I'm moving to a new apartment next week, need to update my shipping address for order #TN-3456", "Entered the wrong zip code during checkout, please correct to 90210", "Need to change delivery from home address to my office address"]},
    {"subject": "Update billing address on file", "category": "address_change", "priority": "medium",
     "messages": ["My company moved offices, need to update the billing address for future invoices", "Billing address on my account is outdated, please update to the new one", "Credit card billing address changed, need to sync it with my account"]},
    {"subject": "Ship to different address than billing", "category": "address_change", "priority": "low",
     "messages": ["Can I have this shipped to my sister's address as a birthday gift?", "Need this order delivered to my warehouse instead of the billing address", "Want to use my secondary address for delivery but keep billing address the same"]},
    {"subject": "Address change for active subscription delivery", "category": "address_change", "priority": "medium",
     "messages": ["Moving to a new city, need my monthly subscription box sent to the new address starting next month", "My subscription is being delivered to my old address, updated my profile but it didn't change the active subscription", "Need to change the delivery address for my recurring order immediately"]},

    # ─── Logistics & Shipping ───
    {"subject": "Express shipping not honored - delivered late", "category": "logistics", "priority": "high",
     "messages": ["Paid $29.99 for next-day delivery but received it 4 days later", "Guaranteed 2-day shipping took 6 days, I want my shipping fee refunded", "The express shipping I paid for was clearly not used, package came via standard ground"]},
    {"subject": "Package damaged during transit", "category": "logistics", "priority": "high",
     "messages": ["The shipping box was crushed and the items inside were damaged, need replacement", "Delivery person left package in the rain, contents are water damaged", "The fragile items were not packed properly and arrived broken"]},
    {"subject": "International shipping customs delay", "category": "logistics", "priority": "medium",
     "messages": ["My international order is stuck at customs for 3 weeks, can you help?", "Need the commercial invoice for customs clearance, wasn't included in the package", "Customs is asking for additional documentation, can you provide it urgently?"]},
    {"subject": "Shipment held at local facility - need pickup", "category": "logistics", "priority": "medium",
     "messages": ["Package is at the local depot for 5 days, no delivery attempt made", "Need to schedule a pickup from the distribution center, where is it located?", "Delivery keeps failing because I'm at work, can I pick it up instead?"]},
    {"subject": "Courier not following delivery instructions", "category": "logistics", "priority": "low",
     "messages": ["Left specific instructions to leave at the back door but courier keeps leaving it at the front", "Requested signature-required delivery but package was left unattended", "Courier keeps marking 'attempted delivery' but I've been home all day"]},
    {"subject": "Split shipment - only received part of order", "category": "logistics", "priority": "medium",
     "messages": ["Order had 5 items but I only received 2, where are the rest?", "Tracking shows only one package but I ordered multiple items", "Received partial shipment with no explanation, need status on remaining items"]},

    # ─── Subscription & Billing (Paddle-related) ───
    {"subject": "Subscription renewed without notice", "category": "billing", "priority": "high",
     "messages": ["My annual subscription auto-renewed and I was charged $299 without any reminder email", "Didn't receive any renewal notice before my card was charged", "Would like to cancel this renewal and get a refund, I didn't authorize it"]},
    {"subject": "Upgrade plan from Starter to Business tier", "category": "billing", "priority": "medium",
     "messages": ["Want to upgrade my subscription to the Business plan, what's the prorated cost?", "Need to upgrade immediately as my team has grown beyond the Starter plan limits", "Can you help me upgrade and apply the prorated credit from my current plan?"]},
    {"subject": "Downgrade subscription to lower tier", "category": "billing", "priority": "medium",
     "messages": ["We're downsizing and need to downgrade from Enterprise to Business tier", "The current plan is too expensive for our needs, want to switch to a lower tier", "How do I downgrade my subscription? Will I lose my data?"]},
    {"subject": "Invoice amount doesn't match agreed pricing", "category": "billing", "priority": "high",
     "messages": ["Our contract says $199/month but the invoice shows $249, please correct this", "The discount we negotiated is not reflected in this month's invoice", "Being charged for 15 seats when we only have 10 active users"]},
    {"subject": "Payment method expiring - need to update card", "category": "billing", "priority": "medium",
     "messages": ["My credit card on file expires next month, how do I update it?", "Need to change our payment method from credit card to bank transfer", "Company switched to a new corporate card, need to update billing details"]},
    {"subject": "Request credit for service outage", "category": "billing", "priority": "high",
     "messages": ["Service was down for 6 hours on Monday, requesting SLA credit for the downtime", "Our SLA guarantees 99.9% uptime, this month we had 2 outages totaling 10 hours", "Need a credit adjustment on our next invoice for the service interruptions"]},
    {"subject": "Tax exemption certificate not applied", "category": "billing", "priority": "medium",
     "messages": ["We're a non-profit and tax-exempt, but our invoices include sales tax", "Submitted our tax exemption certificate last month but still being charged tax", "Need to retroactively remove tax charges from the last 3 invoices"]},
    {"subject": "Cancel subscription immediately", "category": "billing", "priority": "critical",
     "messages": ["Want to cancel our subscription effective immediately, no longer need the service", "Closing our account, please cancel and confirm no further charges", "Switching to a competitor, need immediate cancellation and final invoice"]},

    # ─── Product Cancellation ───
    {"subject": "Cancel my order before it ships", "category": "cancellation", "priority": "high",
     "messages": ["Need to cancel order #TN-9101 immediately, it hasn't shipped yet", "Changed my mind about the purchase, please cancel and refund", "Found a better price elsewhere, want to cancel this order right away"]},
    {"subject": "Cancellation fee seems unfair", "category": "cancellation", "priority": "medium",
     "messages": ["Being charged a 25% cancellation fee which wasn't disclosed at purchase", "The cancellation fee is higher than the product price, this can't be right", "Was never told about any cancellation fee when I signed up"]},
    {"subject": "Service cancelled but still being charged", "category": "cancellation", "priority": "critical",
     "messages": ["Cancelled my subscription 2 months ago but I'm still being billed every month", "Received another charge after cancellation, this is unauthorized", "Cancellation was confirmed via email but the charges keep coming"]},

    # ─── Delivery Issues ───
    {"subject": "Food delivery arrived cold and late", "category": "delivery", "priority": "high",
     "messages": ["Food was delivered 45 minutes late and everything was cold, want a full refund", "The meal was supposed to arrive hot but the delivery took over an hour", "Ordered from a restaurant 5 minutes away, took 90 minutes to arrive"]},
    {"subject": "Delivery driver was unprofessional", "category": "delivery", "priority": "medium",
     "messages": ["The delivery person was rude and threw the package at my door", "Driver refused to come to my apartment, left package at the street gate", "Delivery person called me 5 times during work hours demanding I come outside"]},
    {"subject": "Missing items from delivery order", "category": "delivery", "priority": "high",
     "messages": ["Ordered 6 items but only 4 were in the delivery, missing the main dish", "The side items and drinks are missing from my order, need them delivered or refunded", "Partial delivery received, key items missing and the receipt shows full order"]},

    # ─── SaaS Company Tickets ───
    {"subject": "API rate limit hit during peak hours", "category": "saas_support", "priority": "high",
     "messages": ["Getting 429 errors during our peak traffic hours, need rate limit increased", "Our application is failing because the API rate limit is too low for our usage", "Can we upgrade our API tier? Current limits are blocking our users"]},
    {"subject": "Data export request for compliance audit", "category": "saas_support", "priority": "medium",
     "messages": ["Need a complete data export for our annual compliance audit by end of week", "GDPR data portability request - need all our data in a machine-readable format", "Regulatory audit requires full data dump, including metadata and timestamps"]},
    {"subject": "SSO integration broken after update", "category": "saas_support", "priority": "critical",
     "messages": ["Our Okta SSO stopped working after your latest platform update", "SAML authentication is returning errors, 500+ employees can't log in", "SSO integration was working perfectly until yesterday's maintenance"]},
    {"subject": "Webhook events not being delivered", "category": "saas_support", "priority": "high",
     "messages": ["Our webhook endpoint hasn't received events in 3 days, critical integrations broken", "Webhook delivery failures are not showing up in the dashboard either", "Production workflow depends on webhook events, this is blocking our operations"]},
    {"subject": "Need sandbox environment for testing", "category": "saas_support", "priority": "low",
     "messages": ["Is there a sandbox/test environment where we can test our integration?", "Need to test our webhook handler without affecting production data", "Can you provide test API keys for our staging environment?"]},
    {"subject": "Usage metrics don't match our records", "category": "saas_support", "priority": "medium",
     "messages": ["Dashboard shows 50K API calls but our monitoring says 35K, there's a discrepancy", "The usage report shows 200% of our quota but we've been tracking and we're under 80%", "Billing is based on usage metrics that don't match our internal logs"]},
    {"subject": "Multi-tenant data isolation concern", "category": "saas_support", "priority": "critical",
     "messages": ["Seeing data from another tenant in our API responses, serious security issue", "Our customer reported seeing another company's data in their dashboard", "Data isolation between tenants appears broken, this is a major compliance issue"]},

    # ─── General Customer Care ───
    {"subject": "Loyalty points not credited for recent purchase", "category": "general", "priority": "low",
     "messages": ["Made a $500 purchase last week but no loyalty points were added to my account", "My rewards points balance hasn't updated despite multiple purchases", "Points from my last 3 orders are missing from my rewards account"]},
    {"subject": "Price match request for item found cheaper", "category": "general", "priority": "medium",
     "messages": ["Found the same product $50 cheaper on a competitor's site, do you price match?", "Your price match guarantee - I found this item for less elsewhere", "Can you match the current sale price? I just bought this 2 days ago at full price"]},
    {"subject": "Gift card balance showing incorrect amount", "category": "general", "priority": "medium",
     "messages": ["My gift card should have $150 but it's showing $75, think there's an error", "Used my gift card for a $30 purchase but $100 was deducted", "Gift card balance doesn't match my purchase history, need it corrected"]},
    {"subject": "Need extension on my free trial", "category": "general", "priority": "low",
     "messages": ["Didn't get a chance to fully evaluate during the trial, can I get an extension?", "Our team needs 2 more weeks to properly test the platform", "Free trial expired before we could set it up, requesting a 14-day extension"]},
    {"subject": "Accessibility issue with the mobile app", "category": "general", "priority": "medium",
     "messages": ["Screen reader doesn't work with your mobile app, I'm visually impaired", "Can't navigate the app using voice control, accessibility features seem broken", "The app doesn't meet WCAG guidelines, need accommodation for my disability"]},
    {"subject": "Complaint about rude customer service agent", "category": "complaint", "priority": "high",
     "messages": ["The agent I spoke with yesterday was dismissive and rude, unacceptable", "I was hung up on by your representative after waiting 30 minutes on hold", "Agent refused to escalate my issue and talked over me repeatedly"]},

    # ─── Warranty & Repair ───
    {"subject": "Product under warranty needs repair", "category": "warranty", "priority": "medium",
     "messages": ["My device is still under the 2-year warranty, the battery won't hold a charge", "Need warranty repair for my unit, serial number SN-45291", "Warranty claim for defective product purchased 6 months ago"]},
    {"subject": "Extended warranty claim denied unfairly", "category": "warranty", "priority": "high",
     "messages": ["My extended warranty claim was denied even though the issue is clearly covered", "Paid extra for the extended warranty but they say it's 'normal wear and tear'", "The denial reason doesn't match the actual problem with my product"]},

    # ─── Account Management ───
    {"subject": "Need to merge two accounts created by mistake", "category": "account", "priority": "medium",
     "messages": ["I accidentally created two accounts with different emails, can they be merged?", "Have orders split across two accounts, want everything in one place", "Used work email and personal email for different orders, need to consolidate"]},
    {"subject": "Deceased family member's account closure", "category": "account", "priority": "medium",
     "messages": ["My father passed away, need to close his account and get any remaining balance refunded", "Handling my late spouse's account, need help with closure and data retrieval", "Need to transfer account ownership due to death of the account holder"]},
    {"subject": "Account locked after too many login attempts", "category": "account", "priority": "high",
     "messages": ["My account is locked and I can't reset my password, the email never arrives", "Got locked out after my kid tried logging in multiple times, need access restored", "Account shows as locked, I have urgent orders I need to check on"]},
]

CHANNELS = ["email", "chat", "sms", "voice", "social"]


def seed():
    print("=" * 60)
    print("  PARWA Manual Testing Seed Script")
    print("  Real Customer Care Tickets - Returns, Orders, Logistics,")
    print("  Billing, SaaS Support, Address Changes & More")
    print("=" * 60)

    # Remove old DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("   Removed old database")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # ── Create tables (SQLite compatible) ──
    print("\n1. Creating database tables...")

    c.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT NOT NULL,
            subscription_tier TEXT NOT NULL DEFAULT 'starter',
            subscription_status TEXT DEFAULT 'active',
            mode TEXT DEFAULT 'shadow',
            paddle_customer_id TEXT,
            paddle_subscription_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            phone TEXT,
            avatar_url TEXT,
            role TEXT DEFAULT 'owner',
            is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            is_platform_admin INTEGER DEFAULT 0,
            mfa_enabled INTEGER DEFAULT 0,
            failed_login_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            variant TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            capacity_used INTEGER DEFAULT 0,
            capacity_max INTEGER DEFAULT 100,
            accuracy_rate REAL DEFAULT 0,
            tickets_resolved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS variant_instances (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            instance_name TEXT NOT NULL,
            variant_type TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            channel_assignment TEXT DEFAULT '[]',
            capacity_config TEXT DEFAULT '{}',
            celery_queue_namespace TEXT,
            redis_partition_key TEXT,
            active_tickets_count INTEGER DEFAULT 0,
            total_tickets_handled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            external_id TEXT,
            email TEXT,
            phone TEXT,
            name TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            customer_id TEXT REFERENCES customers(id) ON DELETE SET NULL,
            channel TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            subject TEXT,
            priority TEXT DEFAULT 'medium',
            category TEXT,
            tags TEXT DEFAULT '[]',
            agent_id TEXT REFERENCES agents(id),
            assigned_to TEXT REFERENCES users(id),
            classification_intent TEXT,
            classification_type TEXT,
            metadata_json TEXT DEFAULT '{}',
            reopen_count INTEGER DEFAULT 0,
            frozen INTEGER DEFAULT 0,
            parent_ticket_id TEXT REFERENCES tickets(id),
            duplicate_of_id TEXT REFERENCES tickets(id),
            is_spam INTEGER DEFAULT 0,
            awaiting_human INTEGER DEFAULT 0,
            awaiting_client INTEGER DEFAULT 0,
            escalation_level INTEGER DEFAULT 1,
            sla_breached INTEGER DEFAULT 0,
            plan_snapshot TEXT DEFAULT '{}',
            variant_version TEXT,
            first_response_at TEXT,
            resolution_target_at TEXT,
            client_timezone TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ticket_messages (
            id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            channel TEXT,
            is_internal INTEGER DEFAULT 0,
            is_redacted INTEGER DEFAULT 0,
            ai_confidence REAL,
            variant_version TEXT,
            classification TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS company_settings (
            id TEXT PRIMARY KEY,
            company_id TEXT UNIQUE NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            ooo_status TEXT DEFAULT 'active',
            ooo_message TEXT DEFAULT '',
            brand_voice TEXT DEFAULT 'professional',
            tone_guidelines TEXT DEFAULT '',
            prohibited_phrases TEXT DEFAULT '[]',
            pii_patterns TEXT DEFAULT '[]',
            top_k INTEGER DEFAULT 5,
            similarity_threshold REAL DEFAULT 0.7,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jarvis_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            company_id TEXT REFERENCES companies(id),
            type TEXT DEFAULT 'onboarding',
            context_json TEXT DEFAULT '{}',
            message_count_today INTEGER DEFAULT 0,
            total_message_count INTEGER DEFAULT 0,
            pack_type TEXT DEFAULT 'free',
            is_active INTEGER DEFAULT 1,
            payment_status TEXT DEFAULT 'none',
            handoff_completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jarvis_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES jarvis_sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jarvis_awareness_snapshots (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            company_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            value REAL NOT NULL,
            threshold REAL NOT NULL,
            status TEXT DEFAULT 'healthy',
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jarvis_proactive_alerts (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            company_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            domain TEXT,
            metric_value REAL,
            threshold_value REAL,
            action_suggested TEXT,
            action_taken TEXT,
            acknowledged_at TEXT,
            resolved_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jarvis_commands (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            company_id TEXT NOT NULL,
            raw_input TEXT NOT NULL,
            parsed_command TEXT,
            command_type TEXT,
            target TEXT,
            parameters TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            result TEXT,
            execution_status TEXT DEFAULT 'pending',
            undo_available INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sms_channel_configs (
            id TEXT PRIMARY KEY,
            company_id TEXT UNIQUE NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            twilio_phone_number TEXT,
            twilio_account_sid TEXT,
            twilio_auth_token_encrypted TEXT,
            is_enabled INTEGER DEFAULT 0,
            opt_in_keywords TEXT DEFAULT '["START","YES","OPTIN"]',
            opt_out_keywords TEXT DEFAULT '["STOP","NO","OPTOUT"]',
            rate_limit_per_hour INTEGER DEFAULT 10,
            rate_limit_per_day INTEGER DEFAULT 50,
            auto_reply_opt_in TEXT DEFAULT 'Thanks for opting in! You can text STOP to opt out at any time.',
            auto_reply_opt_out TEXT DEFAULT 'You have been opted out. Text START to opt back in.',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sms_conversations (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            customer_phone TEXT NOT NULL,
            twilio_phone_number TEXT,
            customer_id TEXT REFERENCES customers(id),
            ticket_id TEXT REFERENCES tickets(id),
            consent_status TEXT DEFAULT 'none',
            last_message_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sms_messages (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            conversation_id TEXT NOT NULL REFERENCES sms_conversations(id) ON DELETE CASCADE,
            twilio_message_sid TEXT,
            direction TEXT NOT NULL,
            from_number TEXT,
            to_number TEXT,
            body TEXT,
            status TEXT DEFAULT 'queued',
            segment_count INTEGER DEFAULT 1,
            cost REAL DEFAULT 0,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS voice_call_logs (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            customer_id TEXT REFERENCES customers(id),
            ticket_id TEXT REFERENCES tickets(id),
            twilio_call_sid TEXT,
            from_number TEXT,
            to_number TEXT,
            direction TEXT,
            duration_seconds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'initiated',
            recording_url TEXT,
            transcript TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS paddle_transactions (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            paddle_transaction_id TEXT,
            customer_id TEXT REFERENCES customers(id),
            ticket_id TEXT REFERENCES tickets(id),
            amount REAL,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'pending',
            transaction_type TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS ix_tickets_company ON tickets(company_id);
        CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets(status);
        CREATE INDEX IF NOT EXISTS ix_tickets_priority ON tickets(priority);
        CREATE INDEX IF NOT EXISTS ix_tickets_category ON tickets(category);
        CREATE INDEX IF NOT EXISTS ix_tickets_agent ON tickets(agent_id);
        CREATE INDEX IF NOT EXISTS ix_customers_company ON customers(company_id);
        CREATE INDEX IF NOT EXISTS ix_agents_company ON agents(company_id);
        CREATE INDEX IF NOT EXISTS ix_variant_instances_company ON variant_instances(company_id);
        CREATE INDEX IF NOT EXISTS ix_ticket_messages_ticket ON ticket_messages(ticket_id);
        CREATE INDEX IF NOT EXISTS ix_sms_conversations_company ON sms_conversations(company_id);
        CREATE INDEX IF NOT EXISTS ix_sms_messages_conversation ON sms_messages(conversation_id);
    """)

    print("   Tables created")

    # ── Create Company ──
    print("\n2. Creating test company...")
    company_id = str(uuid.uuid4())
    c.execute("INSERT INTO companies (id, name, industry, subscription_tier, subscription_status, mode) VALUES (?, ?, ?, ?, ?, ?)",
              (company_id, "TechNova Solutions", "technology", "high_volume", "active", "live"))

    # Company settings
    settings_id = str(uuid.uuid4())
    c.execute("INSERT INTO company_settings (id, company_id, brand_voice, ooo_status) VALUES (?, ?, ?, ?)",
              (settings_id, company_id, "friendly_professional", "active"))

    # SMS Channel Config (with Twilio)
    sms_config_id = str(uuid.uuid4())
    c.execute("""INSERT INTO sms_channel_configs 
        (id, company_id, twilio_phone_number, twilio_account_sid, twilio_auth_token_encrypted, is_enabled, 
         rate_limit_per_hour, rate_limit_per_day) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (sms_config_id, company_id, os.environ.get("TWILIO_PHONE_NUMBER", "+919652852014"),
               os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", ""), 1, 20, 100))

    print(f"   Company: TechNova Solutions (id={company_id[:8]}...)")
    print(f"   SMS Config: +919652852014 (Twilio enabled)")

    # ── Create Owner User ──
    print("\n3. Creating owner user...")
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    user_id = str(uuid.uuid4())
    password_hash = pwd_context.hash("TestPass123!")
    c.execute("INSERT INTO users (id, company_id, email, password_hash, full_name, role, is_active, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (user_id, company_id, "owner@technova.com", password_hash, "Priya Sharma", "owner", 1, 1))

    print(f"   User: Priya Sharma (owner@technova.com / TestPass123!)")

    # ── Create 3 Variant Instances ──
    print("\n4. Creating 3 variant instances...")

    variants = [
        {
            "instance_name": "Mini PARWA - Chat Support",
            "variant_type": "mini_parwa",
            "channel_assignment": json.dumps(["chat", "social"]),
            "capacity_config": json.dumps({"max_concurrent": 15, "max_daily": 200}),
            "capacity_max": 50,
            "accuracy_rate": 85.0,
        },
        {
            "instance_name": "PARWA - Email & Voice Support",
            "variant_type": "parwa",
            "channel_assignment": json.dumps(["email", "voice"]),
            "capacity_config": json.dumps({"max_concurrent": 30, "max_daily": 500}),
            "capacity_max": 100,
            "accuracy_rate": 92.0,
        },
        {
            "instance_name": "PARWA High - Critical & Escalations",
            "variant_type": "parwa_high",
            "channel_assignment": json.dumps(["email", "chat", "sms", "voice"]),
            "capacity_config": json.dumps({"max_concurrent": 10, "max_daily": 100}),
            "capacity_max": 25,
            "accuracy_rate": 97.0,
        },
    ]

    agent_records = []
    for v in variants:
        variant_id = str(uuid.uuid4())
        c.execute("INSERT INTO variant_instances (id, company_id, instance_name, variant_type, channel_assignment, capacity_config, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (variant_id, company_id, v["instance_name"], v["variant_type"], v["channel_assignment"], v["capacity_config"], "active"))

        agent_id = str(uuid.uuid4())
        c.execute("INSERT INTO agents (id, company_id, name, variant, status, capacity_max, accuracy_rate) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (agent_id, company_id, v["instance_name"], v["variant_type"], "active", v["capacity_max"], v["accuracy_rate"]))

        agent_records.append({"agent_id": agent_id, "variant_id": variant_id, "variant_type": v["variant_type"]})
        print(f"   Variant: {v['instance_name']} ({v['variant_type']})")

    # ── Create 20 Customers ──
    print("\n5. Creating 20 fake customers...")

    customer_names = [
        ("Rahul Gupta", "rahul.gupta@gmail.com", "+919876543210"),
        ("Sarah Chen", "sarah.chen@outlook.com", "+14155550101"),
        ("Amit Patel", "amit.p@technomail.in", "+918765432109"),
        ("Emily Rodriguez", "emily.r@company.com", "+12125550202"),
        ("Kenji Tanaka", "kenji.t@business.jp", "+81355550100"),
        ("Fatima Al-Rashid", "fatima.ar@enterprise.ae", "+97145550300"),
        ("David Kim", "david.kim@corp.kr", "+8225550400"),
        ("Maria Santos", "maria.s@startup.br", "+551155550500"),
        ("James O'Brien", "james.ob@firm.ie", "+35315550600"),
        ("Wei Zhang", "wei.zhang@tech.cn", "+862155550700"),
        ("Anna Kowalski", "anna.k@services.pl", "+48225550800"),
        ("Carlos Mendez", "carlos.m@negocio.mx", "+525555550900"),
        ("Sophie Dubois", "sophie.d@societe.fr", "+33155551000"),
        ("Olga Petrov", "olga.p@company.ru", "+74955551100"),
        ("Hassan Mahmoud", "hassan.m@biz.eg", "+20255551200"),
        ("Lisa Andersen", "lisa.a@nordic.dk", "+45335551300"),
        ("Ravi Kumar", "ravi.k@infotech.in", "+919988776655"),
        ("Yuki Yamamoto", "yuki.y@office.jp", "+81655551400"),
        ("Benjamin Schmidt", "ben.s@deutch.de", "+493055551500"),
        ("Priya Nair", "priya.n@cloudworks.in", "+918877665544"),
    ]

    customer_ids = []
    for name, email, phone in customer_names:
        cust_id = str(uuid.uuid4())
        c.execute("INSERT INTO customers (id, company_id, name, email, phone, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                  (cust_id, company_id, name, email, phone, json.dumps({"source": "manual_test", "tier": random.choice(["free", "basic", "premium"])})))
        customer_ids.append(cust_id)

    print(f"   Created {len(customer_ids)} customers")

    # ── Create 100 Customer Care Tickets ──
    print("\n6. Creating 100 real customer care tickets...")

    # Distribution: mostly open/in_progress so variants have work to do
    statuses = ["open", "open", "open", "open", "in_progress", "in_progress", "resolved", "closed"]
    ticket_count = 0
    message_count = 0

    # Category to intent mapping for classification
    intent_map = {
        "returns": "return_request",
        "refunds": "refund_request",
        "order_tracking": "order_inquiry",
        "order_details": "order_inquiry",
        "address_change": "address_update",
        "logistics": "shipping_inquiry",
        "billing": "billing_inquiry",
        "cancellation": "cancellation_request",
        "delivery": "delivery_complaint",
        "saas_support": "technical_inquiry",
        "general": "general_inquiry",
        "complaint": "escalation",
        "warranty": "warranty_claim",
        "account": "account_management",
    }

    for i in range(100):
        td = random.choice(TICKET_DATA)
        customer_id = random.choice(customer_ids)

        # Channel: SMS/Voice tickets need phone customers, others get random
        channel = td.get("channel_hint", None)
        if channel is None:
            # Weight channels based on category
            if td["category"] in ("billing", "cancellation", "complaint"):
                channel = random.choice(["email", "voice", "sms"])
            elif td["category"] in ("logistics", "delivery"):
                channel = random.choice(["sms", "chat", "voice"])
            elif td["category"] in ("returns", "refunds"):
                channel = random.choice(["email", "chat", "sms"])
            elif td["category"] == "saas_support":
                channel = random.choice(["email", "chat"])
            else:
                channel = random.choice(CHANNELS)

        priority = td["priority"] if random.random() < 0.7 else random.choice(["low", "medium", "medium", "high", "critical"])
        status = random.choice(statuses)

        # Assign to variant based on priority/channel
        if priority in ("critical",) or td["category"] in ("complaint",):
            agent_info = agent_records[2]  # parwa_high
        elif channel in ("email", "voice"):
            agent_info = agent_records[1]  # parwa
        else:
            agent_info = agent_records[0]  # mini_parwa

        ticket_id = str(uuid.uuid4())
        message = random.choice(td["messages"])

        created_at = (datetime.utcnow() - timedelta(
            hours=random.randint(0, 72),
            minutes=random.randint(0, 59),
        )).isoformat()

        sla_breached = 1 if (status in ("open", "in_progress") and random.random() < 0.15) else 0
        first_response_at = None
        if status in ("in_progress", "resolved", "closed"):
            first_response_at = (datetime.utcnow() - timedelta(minutes=random.randint(1, 300))).isoformat()

        escalation = 3 if (priority == "critical" and status == "open") else random.randint(1, 2)

        classification_intent = intent_map.get(td["category"], "general_inquiry")

        c.execute("""INSERT INTO tickets
            (id, company_id, customer_id, channel, status, subject, priority, category, tags,
             agent_id, classification_intent, metadata_json, reopen_count, sla_breached, escalation_level,
             first_response_at, variant_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, company_id, customer_id, channel, status, td["subject"], priority,
             td["category"], json.dumps([td["category"], channel, priority]), agent_info["agent_id"],
             classification_intent,
             json.dumps({"message": message, "source": "manual_test", "channel": channel}),
             random.randint(0, 2) if status == "open" else 0,
             sla_breached, escalation, first_response_at, agent_info["variant_type"], created_at))

        # Create ticket message (customer's initial message)
        msg_id = str(uuid.uuid4())
        c.execute("""INSERT INTO ticket_messages
            (id, ticket_id, company_id, role, content, channel, is_internal, ai_confidence, variant_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, ticket_id, company_id, "customer", message, channel, 0,
             None, None, created_at))
        message_count += 1

        # For in_progress/resolved tickets, add an AI response
        if status in ("in_progress", "resolved", "closed"):
            ai_msg_id = str(uuid.uuid4())
            ai_responses = {
                "returns": "I've initiated the return process for your order. You'll receive a prepaid return label within 24 hours. Please pack the item securely and drop it off at any authorized shipping location.",
                "refunds": "Your refund has been processed and you should see it in your account within 5-7 business days. I've escalated this to ensure priority processing given the delay.",
                "order_tracking": "I've checked your order status and can see there's a shipping delay. I'm contacting the carrier now for an update and will have tracking information for you within 2 hours.",
                "order_details": "I've found your order details. Let me help you with the modification you need. I'll send you a confirmation once the changes are applied.",
                "address_change": "I've updated the delivery address for your order. The new address will be used for all future deliveries as well. You'll receive a confirmation email shortly.",
                "logistics": "I understand the shipping issue and I'm looking into this right away. I'll coordinate with our logistics team to get this resolved for you.",
                "billing": "I've reviewed your billing concern and can see the discrepancy. Let me correct this for you right away and ensure your next invoice is accurate.",
                "cancellation": "Your cancellation request has been processed. Any pending charges will be reversed within 3-5 business days. Is there anything else I can help with?",
                "delivery": "I apologize for the delivery issue. I'm reaching out to our delivery partner immediately to resolve this. You'll receive an update within the hour.",
                "saas_support": "I've identified the technical issue and our engineering team is working on a fix. I'll keep you updated on the progress and estimated resolution time.",
                "general": "Thank you for reaching out. I'm looking into this for you and will have an update shortly.",
                "complaint": "I sincerely apologize for the experience you've had. This is not the standard we hold ourselves to. I'm escalating this to our senior team and will personally follow up.",
                "warranty": "Your warranty claim has been initiated. I'll send you the shipping instructions for the repair and a case number for tracking.",
                "account": "I can help you with your account. Let me verify a few details and then I'll make the necessary changes for you.",
            }
            ai_response = ai_responses.get(td["category"], "Thank you for reaching out. I'm looking into this for you and will provide an update shortly.")
            c.execute("""INSERT INTO ticket_messages
                (id, ticket_id, company_id, role, content, channel, is_internal, ai_confidence, variant_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ai_msg_id, ticket_id, company_id, "ai", ai_response, channel, 0,
                 round(random.uniform(0.82, 0.98), 2), agent_info["variant_type"],
                 (datetime.utcnow() - timedelta(minutes=random.randint(1, 180))).isoformat()))
            message_count += 1

        ticket_count += 1

    # Update variant ticket counts
    for ar in agent_records:
        count = c.execute("SELECT COUNT(*) FROM tickets WHERE agent_id = ?", (ar["agent_id"],)).fetchone()[0]
        c.execute("UPDATE agents SET capacity_used = ?, tickets_resolved = ? WHERE id = ?",
                  (count, c.execute("SELECT COUNT(*) FROM tickets WHERE agent_id = ? AND status IN ('resolved','closed')", (ar["agent_id"],)).fetchone()[0], ar["agent_id"]))
        c.execute("UPDATE variant_instances SET active_tickets_count = ?, total_tickets_handled = ? WHERE id = ?",
                  (c.execute("SELECT COUNT(*) FROM tickets WHERE agent_id = ? AND status IN ('open','in_progress')", (ar["agent_id"],)).fetchone()[0], count, ar["variant_id"]))

    conn.commit()
    print(f"   Created {ticket_count} tickets with {message_count} messages")

    # ── Print Summary ──
    print("\n" + "=" * 60)
    print("  SEED COMPLETE - Real Customer Care Data Summary")
    print("=" * 60)

    # Count tickets by status
    print("\n  Tickets by Status:")
    for status in ["open", "in_progress", "resolved", "closed"]:
        cnt = c.execute("SELECT COUNT(*) FROM tickets WHERE status = ?", (status,)).fetchone()[0]
        print(f"    {status}: {cnt}")

    # Count tickets by category
    print("\n  Tickets by Category:")
    categories = ["returns", "refunds", "order_tracking", "order_details", "address_change",
                  "logistics", "billing", "cancellation", "delivery", "saas_support",
                  "general", "complaint", "warranty", "account"]
    for cat in categories:
        cnt = c.execute("SELECT COUNT(*) FROM tickets WHERE category = ?", (cat,)).fetchone()[0]
        if cnt > 0:
            print(f"    {cat}: {cnt}")

    # Count tickets by channel
    print("\n  Tickets by Channel:")
    for ch in CHANNELS:
        cnt = c.execute("SELECT COUNT(*) FROM tickets WHERE channel = ?", (ch,)).fetchone()[0]
        print(f"    {ch}: {cnt}")

    # Count tickets by variant
    print("\n  Tickets by Variant:")
    for ar in agent_records:
        cnt = c.execute("SELECT COUNT(*) FROM tickets WHERE agent_id = ?", (ar["agent_id"],)).fetchone()[0]
        print(f"    {ar['variant_type']}: {cnt}")

    print(f"""
  Company:     TechNova Solutions
  Industry:    Technology
  Tier:        high_volume
  Mode:        live

  Owner Login:
    Email:    owner@technova.com
    Password: TestPass123!

  Twilio SMS/Voice: +919652852014 (Configured)
  Paddle Billing:   Configured

  Variants Hired (3):
    1. Mini PARWA - Chat Support     (chat, social)
    2. PARWA - Email & Voice Support  (email, voice)
    3. PARWA High - Critical & Escalations (all channels)

  Customers:   20
  Tickets:     100
    - Categories: returns, refunds, order_tracking, order_details,
                  address_change, logistics, billing, cancellation,
                  delivery, saas_support, general, complaint,
                  warranty, account
    - Channels: email, chat, sms, voice, social
    - Priorities: low, medium, high, critical
    - Statuses: open, in_progress, resolved, closed

  Database: {DB_PATH}
""")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    seed()
