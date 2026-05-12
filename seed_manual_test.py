"""
PARWA Manual Testing Seed Script

Creates a company with 3 variant instances, 20 customers, and 100 fake tickets.
Uses raw SQL with SQLite-compatible types (JSON instead of JSONB).
"""

import os
import sys
import uuid
import random
import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "/home/z/my-project/db/parwa_manual_test.db"

# ── Ticket subjects and messages for realism ──

TICKET_DATA = [
    {"subject": "Cannot login to my account", "category": "tech_support", "priority": "high",
     "messages": ["I've been trying to login for the past hour but it keeps saying invalid credentials", "Reset my password but still can't access my account", "The login page just refreshes without any error message"]},
    {"subject": "Billing charge on cancelled subscription", "category": "billing", "priority": "critical",
     "messages": ["I cancelled my subscription last month but I was charged again", "Why is there a $49.99 charge on my statement after cancellation?", "I have the cancellation confirmation email but still got billed"]},
    {"subject": "Feature request: Dark mode", "category": "feature_request", "priority": "low",
     "messages": ["Would love to see a dark mode option in the app", "My eyes hurt using the app at night, please add dark mode", "Every modern app has dark mode, when can we expect it?"]},
    {"subject": "App crashes on startup", "category": "bug_report", "priority": "critical",
     "messages": ["The app crashes immediately when I open it on my iPhone 15", "Updated to latest version and now it won't even start", "Getting a white screen then crash after splash logo"]},
    {"subject": "How do I export my data?", "category": "general", "priority": "medium",
     "messages": ["I need to export all my data for compliance purposes", "Where is the data export feature? Can't find it in settings", "Need a CSV export of all my transaction history"]},
    {"subject": "Very slow response times today", "category": "complaint", "priority": "high",
     "messages": ["Everything is taking 10+ seconds to load today, unacceptable", "The dashboard is practically unusable right now", "Is there an outage? My team can't work like this"]},
    {"subject": "Upgrade my plan to Enterprise", "category": "billing", "priority": "medium",
     "messages": ["We want to upgrade from Growth to Enterprise tier", "Need more variant capacity, how do we upgrade?", "Can you walk me through the Enterprise plan features?"]},
    {"subject": "API returning 500 errors", "category": "bug_report", "priority": "critical",
     "messages": ["Our integration is completely broken, getting 500 errors on every request", "The /api/v1/tickets endpoint is returning 500 Internal Server Error", "This is blocking our production workflow, need urgent fix"]},
    {"subject": "Can I get a refund for last month?", "category": "billing", "priority": "medium",
     "messages": ["The service was down for 3 days last month, I want a refund", "Downtime caused us real business losses, requesting full refund", "Our SLA guarantees 99.9% uptime, we got maybe 95% last month"]},
    {"subject": "SSO integration with Okta", "category": "feature_request", "priority": "medium",
     "messages": ["We need SSO integration with our Okta directory", "Our security team requires SAML/SSO before we can adopt the platform", "Do you support SSO? We use Okta for all our SaaS tools"]},
    {"subject": "Two-factor authentication not working", "category": "tech_support", "priority": "high",
     "messages": ["I enabled 2FA but the codes aren't being accepted", "My authenticator app codes keep getting rejected", "Locked out of my account because 2FA isn't working"]},
    {"subject": "Data migration assistance needed", "category": "general", "priority": "medium",
     "messages": ["We're moving from Zendesk, need help migrating 50k tickets", "Can your team help us import our historical support data?", "Need a timeline for data migration from our old system"]},
    {"subject": "Webhook not triggering", "category": "bug_report", "priority": "high",
     "messages": ["Our webhook endpoint hasn't received any events in 2 days", "Webhook deliveries are failing silently, no error logs on your side", "The webhook URL is correct but we're not getting any POST requests"]},
    {"subject": "Custom domain setup help", "category": "tech_support", "priority": "low",
     "messages": ["How do I set up support.mycompany.com?", "Need help configuring DNS records for custom domain", "CNAME is set up but the custom domain isn't working yet"]},
    {"subject": "Invoice doesn't match our PO", "category": "billing", "priority": "medium",
     "messages": ["The invoice amount doesn't match our purchase order", "We were quoted a different price by your sales team", "Need a corrected invoice with PO number 4521-ABC"]},
    {"subject": "Mobile app notifications not working", "category": "bug_report", "priority": "medium",
     "messages": ["Push notifications stopped working after last update", "I'm not getting any ticket alerts on my phone", "Notification settings are enabled but nothing comes through"]},
    {"subject": "Complaint about support quality", "category": "complaint", "priority": "high",
     "messages": ["Your AI agent gave completely wrong information about our billing", "The bot kept looping and never connected us to a human", "This is the third time the AI has misunderstood our issue"]},
    {"subject": "Need more user seats", "category": "billing", "priority": "low",
     "messages": ["We need to add 10 more team members, how does that work?", "Current seat limit is too low for our growing team", "Can we get additional seats without changing our plan?"]},
    {"subject": "Integration with Salesforce", "category": "feature_request", "priority": "medium",
     "messages": ["Need Salesforce CRM integration for our support workflow", "When will Salesforce integration be available?", "Our sales team needs ticket data synced to Salesforce"]},
    {"subject": "Security vulnerability report", "category": "complaint", "priority": "critical",
     "messages": ["Found an XSS vulnerability in the chat widget", "There's a potential data leak in the API response headers", "Our pentest revealed security issues that need immediate attention"]},
    {"subject": "Password reset email not received", "category": "tech_support", "priority": "high",
     "messages": ["Clicked reset password 5 times, no email received", "Check spam folder too, nothing there", "It's been 2 hours since I requested the reset"]},
    {"subject": "Dashboard analytics incorrect", "category": "bug_report", "priority": "medium",
     "messages": ["The response time graph shows negative values", "Ticket count doesn't match actual tickets in the queue", "SLA compliance percentage is clearly wrong, showing 110%"]},
    {"subject": "Request for SLA documentation", "category": "general", "priority": "low",
     "messages": ["Need a copy of our current SLA agreement", "Can you send me the SLA terms for Enterprise tier?", "What's the guaranteed uptime and response time in our plan?"]},
    {"subject": "Channel configuration issue", "category": "tech_support", "priority": "medium",
     "messages": ["Email channel stopped receiving messages", "SMS channel is sending duplicate messages", "Chat widget shows offline even though we're active"]},
    {"subject": "Unauthorized charge on corporate card", "category": "billing", "priority": "critical",
     "messages": ["We see a charge we never authorized on our corporate card", "Someone used our card without permission, need immediate investigation", "This looks like fraud, we need the charge reversed ASAP"]},
    {"subject": "Chat widget customization", "category": "feature_request", "priority": "low",
     "messages": ["Can we customize the chat widget colors to match our brand?", "Need to add our logo to the chat widget", "Want to change the chat widget greeting message"]},
    {"subject": "Team member can't access dashboard", "category": "tech_support", "priority": "medium",
     "messages": ["Added a new team member but they can't see the dashboard", "My colleague gets 403 Forbidden when accessing reports", "Role permissions seem broken, admin can't access settings"]},
    {"subject": "Bulk delete old tickets", "category": "general", "priority": "low",
     "messages": ["How can I bulk delete tickets older than 6 months?", "Need to clean up our ticket archive, too many old tickets", "Is there a way to archive tickets instead of deleting?"]},
    {"subject": "Audio quality issues on voice calls", "category": "complaint", "priority": "high",
     "messages": ["Voice calls have terrible audio quality, lots of static", "Customers are complaining they can't hear our agents", "The voice channel sounds like we're underwater"]},
    {"subject": "Need priority support escalation path", "category": "general", "priority": "medium",
     "messages": ["What's the escalation path for critical issues?", "How do we reach a human agent when the AI can't help?", "Need a direct phone line for production emergencies"]},
]

CHANNELS = ["email", "chat", "sms", "voice", "social"]


def seed():
    print("=" * 60)
    print("  PARWA Manual Testing Seed Script")
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

        CREATE INDEX IF NOT EXISTS ix_tickets_company ON tickets(company_id);
        CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets(status);
        CREATE INDEX IF NOT EXISTS ix_tickets_priority ON tickets(priority);
        CREATE INDEX IF NOT EXISTS ix_tickets_agent ON tickets(agent_id);
        CREATE INDEX IF NOT EXISTS ix_customers_company ON customers(company_id);
        CREATE INDEX IF NOT EXISTS ix_agents_company ON agents(company_id);
        CREATE INDEX IF NOT EXISTS ix_variant_instances_company ON variant_instances(company_id);
    """)

    print("   ✓ Tables created")

    # ── Create Company ──
    print("\n2. Creating test company...")
    company_id = str(uuid.uuid4())
    c.execute("INSERT INTO companies (id, name, industry, subscription_tier, subscription_status, mode) VALUES (?, ?, ?, ?, ?, ?)",
              (company_id, "TechNova Solutions", "technology", "high_volume", "active", "live"))

    # Company settings
    settings_id = str(uuid.uuid4())
    c.execute("INSERT INTO company_settings (id, company_id, brand_voice, ooo_status) VALUES (?, ?, ?, ?)",
              (settings_id, company_id, "friendly_professional", "active"))

    print(f"   ✓ Company: TechNova Solutions (id={company_id[:8]}...)")

    # ── Create Owner User ──
    print("\n3. Creating owner user...")
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    user_id = str(uuid.uuid4())
    password_hash = pwd_context.hash("TestPass123!")
    c.execute("INSERT INTO users (id, company_id, email, password_hash, full_name, role, is_active, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (user_id, company_id, "owner@technova.com", password_hash, "Priya Sharma", "owner", 1, 1))

    print(f"   ✓ User: Priya Sharma (owner@technova.com / TestPass123!)")

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
        print(f"   ✓ Variant: {v['instance_name']} ({v['variant_type']})")

    # ── Create 20 Customers ──
    print("\n5. Creating 20 fake customers...")

    customer_names = [
        ("Rahul Gupta", "rahul.gupta@gmail.com", "+91-98765-43210"),
        ("Sarah Chen", "sarah.chen@outlook.com", "+1-415-555-0101"),
        ("Amit Patel", "amit.p@technomail.in", "+91-87654-32109"),
        ("Emily Rodriguez", "emily.r@company.com", "+1-212-555-0202"),
        ("Kenji Tanaka", "kenji.t@business.jp", "+81-3-5555-0100"),
        ("Fatima Al-Rashid", "fatima.ar@enterprise.ae", "+971-4-555-0300"),
        ("David Kim", "david.kim@corp.kr", "+82-2-555-0400"),
        ("Maria Santos", "maria.s@startup.br", "+55-11-5555-0500"),
        ("James O'Brien", "james.ob@firm.ie", "+353-1-555-0600"),
        ("Wei Zhang", "wei.zhang@tech.cn", "+86-21-5555-0700"),
        ("Anna Kowalski", "anna.k@services.pl", "+48-22-555-0800"),
        ("Carlos Mendez", "carlos.m@negocio.mx", "+52-55-5555-0900"),
        ("Sophie Dubois", "sophie.d@societe.fr", "+33-1-5555-1000"),
        ("Olga Petrov", "olga.p@company.ru", "+7-495-555-1100"),
        ("Hassan Mahmoud", "hassan.m@biz.eg", "+20-2-5555-1200"),
        ("Lisa Andersen", "lisa.a@nordic.dk", "+45-33-555-1300"),
        ("Ravi Kumar", "ravi.k@infotech.in", "+91-99887-76655"),
        ("Yuki Yamamoto", "yuki.y@office.jp", "+81-6-5555-1400"),
        ("Benjamin Schmidt", "ben.s@deutch.de", "+49-30-5555-1500"),
        ("Priya Nair", "priya.n@cloudworks.in", "+91-88776-65544"),
    ]

    customer_ids = []
    for name, email, phone in customer_names:
        cust_id = str(uuid.uuid4())
        c.execute("INSERT INTO customers (id, company_id, name, email, phone, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                  (cust_id, company_id, name, email, phone, json.dumps({"source": "manual_test", "tier": random.choice(["free", "basic", "premium"])})))
        customer_ids.append(cust_id)

    print(f"   ✓ Created {len(customer_ids)} customers")

    # ── Create 100 Tickets ──
    print("\n6. Creating 100 fake support tickets...")

    statuses = ["open", "open", "open", "in_progress", "in_progress", "resolved", "closed"]
    ticket_count = 0

    for i in range(100):
        td = random.choice(TICKET_DATA)
        customer_id = random.choice(customer_ids)
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

        c.execute("""INSERT INTO tickets
            (id, company_id, customer_id, channel, status, subject, priority, category, tags,
             agent_id, metadata_json, reopen_count, sla_breached, escalation_level,
             first_response_at, variant_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, company_id, customer_id, channel, status, td["subject"], priority,
             td["category"], json.dumps([td["category"], channel]), agent_info["agent_id"],
             json.dumps({"message": message, "source": "manual_test"}),
             random.randint(0, 2) if status == "open" else 0,
             sla_breached, escalation, first_response_at, agent_info["variant_type"], created_at))

        ticket_count += 1

    # Update variant ticket counts
    for ar in agent_records:
        count = c.execute("SELECT COUNT(*) FROM tickets WHERE agent_id = ?", (ar["agent_id"],)).fetchone()[0]
        c.execute("UPDATE agents SET capacity_used = ?, tickets_resolved = ? WHERE id = ?",
                  (count, c.execute("SELECT COUNT(*) FROM tickets WHERE agent_id = ? AND status IN ('resolved','closed')", (ar["agent_id"],)).fetchone()[0], ar["agent_id"]))
        c.execute("UPDATE variant_instances SET active_tickets_count = ?, total_tickets_handled = ? WHERE id = ?",
                  (c.execute("SELECT COUNT(*) FROM tickets WHERE agent_id = ? AND status IN ('open','in_progress')", (ar["agent_id"],)).fetchone()[0], count, ar["variant_id"]))

    conn.commit()
    print(f"   ✓ Created {ticket_count} tickets")

    # ── Print Summary ──
    print("\n" + "=" * 60)
    print("  SEED COMPLETE — Manual Testing Data Summary")
    print("=" * 60)

    # Count tickets by status
    for status in ["open", "in_progress", "resolved", "closed"]:
        cnt = c.execute("SELECT COUNT(*) FROM tickets WHERE status = ?", (status,)).fetchone()[0]
        print(f"    {status}: {cnt} tickets")

    print(f"""
  Company:     TechNova Solutions
  Industry:    Technology
  Tier:        high_volume
  Mode:        live

  Owner Login:
    Email:    owner@technova.com
    Password: TestPass123!

  Variants Hired (3):
    1. Mini PARWA - Chat Support     (chat, social)
    2. PARWA - Email & Voice Support  (email, voice)
    3. PARWA High - Critical & Escalations (all channels)

  Customers:   20
  Tickets:     100
    - Mix of: tech_support, billing, feature_request,
              bug_report, general, complaint
    - Channels: email, chat, sms, voice, social
    - Priorities: low, medium, high, critical
    - Statuses: open, in_progress, resolved, closed
    - Some SLA-breached tickets for Jarvis awareness

  Database: {DB_PATH}
""")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    seed()
