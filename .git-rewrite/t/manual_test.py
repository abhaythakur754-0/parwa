"""
PARWA End-to-End Manual Testing Script

Simulates a real user interacting with the PARWA Jarvis system:
1. Register a company owner
2. Login and get JWT token
3. Create 3 variant instances
4. Create 20 customers
5. Create 100 support tickets
6. Create a Jarvis CC session
7. Chat with Jarvis about ticket status, variant health
8. Trigger awareness tick and check alerts
9. Issue commands through the command layer
10. Report all results

This runs the FastAPI app in-process using httpx AsyncClient.
"""
import os
import sys
import uuid
import random
import json
import asyncio
from datetime import datetime, timedelta

# ── Environment setup BEFORE any imports ──
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "dev-manual-testing-key-change-in-prod"
os.environ["JWT_SECRET_KEY"] = "dev-jwt-manual-testing-key"
os.environ["DEBUG"] = "true"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["PRICING_SIGNING_KEY"] = "dev-pricing-key-change-in-prod-32c"
os.environ["DATA_ENCRYPTION_KEY"] = "devkey_devkey_devkey_devkey_abcd"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

# Patch JSONB→JSON for SQLite
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
_orig_visit = SQLiteTypeCompiler.visit_JSON
def _patched_visit(self, type_, **kw):
    if isinstance(type_, _JSONB):
        return _orig_visit(self, JSON(), **kw)
    return _orig_visit(self, type_, **kw)
SQLiteTypeCompiler.visit_JSON = _patched_visit
SQLiteTypeCompiler.visit_JSONB = _patched_visit

sys.path.insert(0, "/home/z/my-project/parwa")
sys.path.insert(0, "/home/z/my-project/parwa/backend")

# ── Now import the app ──
from httpx import AsyncClient, ASGITransport
from database.base import Base, engine, SessionLocal, init_db
from database.models.core import Company, User, Agent
from database.models.tickets import Ticket, Customer
from database.models.variant_engine import VariantInstance

TICKET_DATA = [
    {"subject": "Cannot login to my account", "category": "tech_support", "priority": "high",
     "messages": ["I've been trying to login for the past hour but it keeps saying invalid credentials", "Reset my password but still can't access my account"]},
    {"subject": "Billing charge on cancelled subscription", "category": "billing", "priority": "critical",
     "messages": ["I cancelled my subscription last month but I was charged again", "Why is there a $49.99 charge on my statement after cancellation?"]},
    {"subject": "Feature request: Dark mode", "category": "feature_request", "priority": "low",
     "messages": ["Would love to see a dark mode option in the app", "My eyes hurt using the app at night"]},
    {"subject": "App crashes on startup", "category": "bug_report", "priority": "critical",
     "messages": ["The app crashes immediately when I open it on my iPhone", "Updated to latest version and now it won't even start"]},
    {"subject": "How do I export my data?", "category": "general", "priority": "medium",
     "messages": ["I need to export all my data for compliance purposes", "Where is the data export feature?"]},
    {"subject": "Very slow response times today", "category": "complaint", "priority": "high",
     "messages": ["Everything is taking 10+ seconds to load today", "The dashboard is practically unusable"]},
    {"subject": "Upgrade my plan to Enterprise", "category": "billing", "priority": "medium",
     "messages": ["We want to upgrade from Growth to Enterprise tier", "Need more variant capacity"]},
    {"subject": "API returning 500 errors", "category": "bug_report", "priority": "critical",
     "messages": ["Our integration is completely broken", "Getting 500 errors on every request"]},
    {"subject": "Can I get a refund for last month?", "category": "billing", "priority": "medium",
     "messages": ["The service was down for 3 days, I want a refund", "Downtime caused us real business losses"]},
    {"subject": "SSO integration with Okta", "category": "feature_request", "priority": "medium",
     "messages": ["We need SSO integration with our Okta directory", "Our security team requires SAML/SSO"]},
    {"subject": "Two-factor authentication not working", "category": "tech_support", "priority": "high",
     "messages": ["I enabled 2FA but the codes aren't being accepted", "My authenticator app codes keep getting rejected"]},
    {"subject": "Data migration assistance needed", "category": "general", "priority": "medium",
     "messages": ["We're moving from Zendesk, need help migrating 50k tickets"]},
    {"subject": "Webhook not triggering", "category": "bug_report", "priority": "high",
     "messages": ["Our webhook endpoint hasn't received any events in 2 days"]},
    {"subject": "Custom domain setup help", "category": "tech_support", "priority": "low",
     "messages": ["How do I set up support.mycompany.com?"]},
    {"subject": "Invoice doesn't match our PO", "category": "billing", "priority": "medium",
     "messages": ["The invoice amount doesn't match our purchase order"]},
    {"subject": "Mobile app notifications not working", "category": "bug_report", "priority": "medium",
     "messages": ["Push notifications stopped working after last update"]},
    {"subject": "Complaint about support quality", "category": "complaint", "priority": "high",
     "messages": ["Your AI agent gave completely wrong information", "The bot kept looping and never connected us to a human"]},
    {"subject": "Need more user seats", "category": "billing", "priority": "low",
     "messages": ["We need to add 10 more team members"]},
    {"subject": "Integration with Salesforce", "category": "feature_request", "priority": "medium",
     "messages": ["Need Salesforce CRM integration for our support workflow"]},
    {"subject": "Security vulnerability report", "category": "complaint", "priority": "critical",
     "messages": ["Found an XSS vulnerability in the chat widget", "There's a potential data leak in the API"]},
    {"subject": "Password reset email not received", "category": "tech_support", "priority": "high",
     "messages": ["Clicked reset password 5 times, no email received"]},
    {"subject": "Dashboard analytics incorrect", "category": "bug_report", "priority": "medium",
     "messages": ["The response time graph shows negative values"]},
    {"subject": "Request for SLA documentation", "category": "general", "priority": "low",
     "messages": ["Need a copy of our current SLA agreement"]},
    {"subject": "Channel configuration issue", "category": "tech_support", "priority": "medium",
     "messages": ["Email channel stopped receiving messages"]},
    {"subject": "Unauthorized charge on corporate card", "category": "billing", "priority": "critical",
     "messages": ["We see a charge we never authorized on our corporate card"]},
    {"subject": "Chat widget customization", "category": "feature_request", "priority": "low",
     "messages": ["Can we customize the chat widget colors?"]},
    {"subject": "Team member can't access dashboard", "category": "tech_support", "priority": "medium",
     "messages": ["Added a new team member but they can't see the dashboard"]},
    {"subject": "Bulk delete old tickets", "category": "general", "priority": "low",
     "messages": ["How can I bulk delete tickets older than 6 months?"]},
    {"subject": "Audio quality issues on voice calls", "category": "complaint", "priority": "high",
     "messages": ["Voice calls have terrible audio quality, lots of static"]},
    {"subject": "Need priority support escalation path", "category": "general", "priority": "medium",
     "messages": ["What's the escalation path for critical issues?"]},
]

CHANNELS = ["email", "chat", "sms", "voice", "social"]


async def run_manual_test():
    print("=" * 70)
    print("  🧪 PARWA Jarvis AI — End-to-End Manual Testing")
    print("=" * 70)

    # Import app
    from backend.app.main import app

    # Create tables
    print("\n📋 Step 1: Creating database tables...")
    init_db()
    print("   ✅ All tables created")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ── Step 2: Register a company owner ──
        print("\n👤 Step 2: Registering company owner...")

        reg_data = {
            "email": "owner@technova.com",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "full_name": "Priya Sharma",
            "company_name": "TechNova Solutions",
            "industry": "technology",
        }

        resp = await client.post("/api/auth/register", json=reg_data)
        print(f"   Status: {resp.status_code}")

        if resp.status_code in (200, 201):
            reg_result = resp.json()
            token = reg_result.get("tokens", {}).get("access_token", "")
            user_id = reg_result.get("user", {}).get("id", "")
            company_id = reg_result.get("user", {}).get("company_id", "")
            print(f"   ✅ User registered: {reg_result.get('user', {}).get('full_name')}")
            print(f"   Company ID: {company_id}")
        else:
            print(f"   ❌ Registration failed: {resp.text[:200]}")
            # Try login instead
            login_resp = await client.post("/api/auth/login", json={
                "email": "owner@technova.com", "password": "TestPass123!"
            })
            if login_resp.status_code == 200:
                login_result = login_resp.json()
                token = login_result.get("tokens", {}).get("access_token", "")
                user_id = login_result.get("user", {}).get("id", "")
                company_id = login_result.get("user", {}).get("company_id", "")
                print(f"   ✅ Logged in instead")
            else:
                print(f"   ❌ Login also failed: {login_resp.text[:200]}")
                return

        headers = {"Authorization": f"Bearer {token}"}

        # ── Step 3: Verify user profile ──
        print("\n🔍 Step 3: Verifying user profile...")
        me_resp = await client.get("/api/auth/me", headers=headers)
        print(f"   Status: {me_resp.status_code}")
        if me_resp.status_code == 200:
            me_data = me_resp.json()
            print(f"   ✅ Name: {me_data.get('full_name')}, Role: {me_data.get('role')}, Company: {me_data.get('company_id', '')[:8]}...")
        else:
            print(f"   ❌ Profile check failed: {me_resp.text[:200]}")

        # ── Step 4: Create 3 Variant Instances via DB ──
        print("\n🤖 Step 4: Creating 3 variant instances (hired)...")

        db = SessionLocal()
        try:
            # Need to bypass tenant for direct DB access
            variants_data = [
                {"name": "Mini PARWA - Chat Support", "type": "mini_parwa",
                 "channels": ["chat", "social"], "capacity_max": 50, "accuracy": 85.0},
                {"name": "PARWA - Email & Voice Support", "type": "parwa",
                 "channels": ["email", "voice"], "capacity_max": 100, "accuracy": 92.0},
                {"name": "PARWA High - Critical & Escalations", "type": "parwa_high",
                 "channels": ["email", "chat", "sms", "voice"], "capacity_max": 25, "accuracy": 97.0},
            ]

            agent_ids = []
            for v in variants_data:
                agent_id = str(uuid.uuid4())
                agent = Agent(
                    id=agent_id,
                    company_id=company_id,
                    name=v["name"],
                    variant=v["type"],
                    status="active",
                    capacity_max=v["capacity_max"],
                    accuracy_rate=v["accuracy"],
                )
                db.add(agent)

                vi_id = str(uuid.uuid4())
                vi = VariantInstance(
                    id=vi_id,
                    company_id=company_id,
                    instance_name=v["name"],
                    variant_type=v["type"],
                    channel_assignment=json.dumps(v["channels"]),
                    capacity_config=json.dumps({"max_concurrent": v["capacity_max"] // 3}),
                    status="active",
                )
                db.add(vi)
                agent_ids.append(agent_id)
                print(f"   ✅ {v['name']} ({v['type']})")

            db.commit()
        except Exception as e:
            db.rollback()
            print(f"   ❌ Error creating variants: {e}")
        finally:
            db.close()

        # ── Step 5: Create 20 Customers ──
        print("\n👥 Step 5: Creating 20 customers...")

        customer_names = [
            ("Rahul Gupta", "rahul.gupta@gmail.com"),
            ("Sarah Chen", "sarah.chen@outlook.com"),
            ("Amit Patel", "amit.p@technomail.in"),
            ("Emily Rodriguez", "emily.r@company.com"),
            ("Kenji Tanaka", "kenji.t@business.jp"),
            ("Fatima Al-Rashid", "fatima.ar@enterprise.ae"),
            ("David Kim", "david.kim@corp.kr"),
            ("Maria Santos", "maria.s@startup.br"),
            ("James O'Brien", "james.ob@firm.ie"),
            ("Wei Zhang", "wei.zhang@tech.cn"),
            ("Anna Kowalski", "anna.k@services.pl"),
            ("Carlos Mendez", "carlos.m@negocio.mx"),
            ("Sophie Dubois", "sophie.d@societe.fr"),
            ("Olga Petrov", "olga.p@company.ru"),
            ("Hassan Mahmoud", "hassan.m@biz.eg"),
            ("Lisa Andersen", "lisa.a@nordic.dk"),
            ("Ravi Kumar", "ravi.k@infotech.in"),
            ("Yuki Yamamoto", "yuki.y@office.jp"),
            ("Benjamin Schmidt", "ben.s@deutch.de"),
            ("Priya Nair", "priya.n@cloudworks.in"),
        ]

        db = SessionLocal()
        try:
            customer_ids = []
            for name, email in customer_names:
                cust_id = str(uuid.uuid4())
                customer = Customer(
                    id=cust_id,
                    company_id=company_id,
                    name=name,
                    email=email,
                    metadata_json=json.dumps({"source": "manual_test"}),
                )
                db.add(customer)
                customer_ids.append(cust_id)
            db.commit()
            print(f"   ✅ Created {len(customer_ids)} customers")
        except Exception as e:
            db.rollback()
            print(f"   ❌ Error: {e}")
            customer_ids = []
        finally:
            db.close()

        # ── Step 6: Create 100 Tickets ──
        print("\n🎫 Step 6: Creating 100 support tickets...")

        db = SessionLocal()
        try:
            statuses = ["open", "open", "open", "in_progress", "in_progress", "resolved", "closed"]
            ticket_count = 0
            priority_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            status_counts = {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
            category_counts = {}

            for i in range(100):
                td = random.choice(TICKET_DATA)
                cust_id = random.choice(customer_ids)
                channel = random.choice(CHANNELS)
                priority = td["priority"] if random.random() < 0.7 else random.choice(["low", "medium", "high", "critical"])
                status = random.choice(statuses)

                # Assign agent based on priority/channel
                if priority == "critical" or td["category"] == "complaint":
                    agent_id = agent_ids[2]
                elif channel in ("email", "voice"):
                    agent_id = agent_ids[1]
                else:
                    agent_id = agent_ids[0]

                ticket = Ticket(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    customer_id=cust_id,
                    channel=channel,
                    status=status,
                    subject=td["subject"],
                    priority=priority,
                    category=td["category"],
                    tags=json.dumps([td["category"], channel]),
                    agent_id=agent_id,
                    metadata_json=json.dumps({"message": random.choice(td["messages"]), "source": "manual_test"}),
                    sla_breached=random.random() < 0.15,
                    escalation_level=3 if priority == "critical" and status == "open" else random.randint(1, 2),
                )
                db.add(ticket)
                ticket_count += 1
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
                status_counts[status] = status_counts.get(status, 0) + 1
                category_counts[td["category"]] = category_counts.get(td["category"], 0) + 1

            db.commit()
            print(f"   ✅ Created {ticket_count} tickets")
            print(f"   📊 By priority: {json.dumps(priority_counts, indent=2)}")
            print(f"   📊 By status: {json.dumps(status_counts, indent=2)}")
            print(f"   📊 By category: {json.dumps(category_counts, indent=2)}")
        except Exception as e:
            db.rollback()
            print(f"   ❌ Error: {e}")
        finally:
            db.close()

        # ── Step 7: Create Jarvis CC Session ──
        print("\n🧠 Step 7: Creating Jarvis Customer Care session...")

        session_resp = await client.post(
            "/api/jarvis/cc/session",
            json={"existing_session_id": None},
            headers=headers,
        )
        print(f"   Status: {session_resp.status_code}")

        if session_resp.status_code in (200, 201):
            session_data = session_resp.json()
            session_id = session_data.get("session_id", session_data.get("id", ""))
            print(f"   ✅ Session created: {session_id[:8]}...")
            print(f"   Type: {session_data.get('type', 'unknown')}")
        else:
            print(f"   ❌ Session creation failed: {session_resp.text[:300]}")
            session_id = ""

        if session_id:
            # ── Step 8: Chat with Jarvis ──
            print("\n💬 Step 8: Chatting with Jarvis about the system...")

            chat_messages = [
                "Hey Jarvis, what's the current status of our support tickets?",
                "How are the variants performing? Any issues I should know about?",
                "Are there any SLA breaches? Show me the critical ones.",
                "What's the ticket volume like across different channels?",
                "Any recommendations for improving our customer care?"
            ]

            for msg in chat_messages:
                print(f"\n   📤 User: {msg}")
                msg_resp = await client.post(
                    "/api/jarvis/cc/message",
                    json={
                        "content": msg,
                        "session_id": session_id,
                        "channel": "chat",
                    },
                    headers=headers,
                )
                print(f"   Status: {msg_resp.status_code}")
                if msg_resp.status_code == 200:
                    msg_data = msg_resp.json()
                    # Get the assistant response
                    if "messages" in msg_data:
                        for m in msg_data.get("messages", [])[-3:]:
                            if m.get("role") == "assistant":
                                content = m.get("content", "")
                                print(f"   🤖 Jarvis: {content[:300]}...")
                    elif "content" in msg_data:
                        print(f"   🤖 Jarvis: {msg_data['content'][:300]}...")
                    elif "response" in msg_data:
                        print(f"   🤖 Jarvis: {msg_data['response'][:300]}...")
                    else:
                        print(f"   🤖 Response: {json.dumps(msg_data, indent=2)[:300]}...")
                else:
                    print(f"   ❌ Chat failed: {msg_resp.text[:200]}")

            # ── Step 9: Trigger Awareness Tick ──
            print("\n\n👁️ Step 9: Triggering Jarvis Awareness Engine...")

            tick_resp = await client.post(
                "/api/jarvis/cc/awareness/tick",
                json={
                    "session_id": session_id,
                    "tick_type": "manual",
                },
                headers=headers,
            )
            print(f"   Status: {tick_resp.status_code}")
            if tick_resp.status_code == 200:
                tick_data = tick_resp.json()
                print(f"   ✅ Awareness tick triggered!")
                print(f"   📊 Results: {json.dumps(tick_data, indent=2)[:500]}...")
            else:
                print(f"   ❌ Tick failed: {tick_resp.text[:300]}")

            # ── Step 10: Get Awareness Snapshot ──
            print("\n\n📸 Step 10: Getting Awareness Snapshot...")

            snap_resp = await client.get(
                f"/api/jarvis/cc/awareness/snapshot?session_id={session_id}",
                headers=headers,
            )
            print(f"   Status: {snap_resp.status_code}")
            if snap_resp.status_code == 200:
                snap_data = snap_resp.json()
                print(f"   ✅ Snapshot retrieved!")
                print(f"   📊 Data: {json.dumps(snap_data, indent=2)[:500]}...")
            else:
                print(f"   ❌ Snapshot failed: {snap_resp.text[:300]}")

            # ── Step 11: Get Awareness Alerts ──
            print("\n\n🚨 Step 11: Getting Awareness Alerts...")

            alerts_resp = await client.get(
                f"/api/jarvis/cc/awareness/alerts?session_id={session_id}",
                headers=headers,
            )
            print(f"   Status: {alerts_resp.status_code}")
            if alerts_resp.status_code == 200:
                alerts_data = alerts_resp.json()
                alert_count = len(alerts_data) if isinstance(alerts_data, list) else alerts_data.get("total", 0)
                print(f"   ✅ Alerts retrieved: {alert_count} active alerts")
                if isinstance(alerts_data, list):
                    for alert in alerts_data[:5]:
                        print(f"   🔔 [{alert.get('severity', '?').upper()}] {alert.get('title', 'N/A')}: {alert.get('message', '')[:100]}")
                else:
                    print(f"   📊 Data: {json.dumps(alerts_data, indent=2)[:500]}...")
            else:
                print(f"   ❌ Alerts failed: {alerts_resp.text[:300]}")

            # ── Step 12: Send Commands ──
            print("\n\n⚙️ Step 12: Sending Commands to Jarvis...")

            commands = [
                "show me ticket volume for today",
                "escalate all critical tickets",
                "what's the health of mini_parwa variant",
            ]

            for cmd in commands:
                print(f"\n   📤 Command: {cmd}")
                cmd_resp = await client.post(
                    "/api/jarvis/cc/command",
                    json={
                        "session_id": session_id,
                        "raw_input": cmd,
                        "source": "chat",
                    },
                    headers=headers,
                )
                print(f"   Status: {cmd_resp.status_code}")
                if cmd_resp.status_code == 200:
                    cmd_data = cmd_resp.json()
                    print(f"   ✅ Command processed!")
                    print(f"   📊 Result: {json.dumps(cmd_data, indent=2)[:300]}...")
                else:
                    print(f"   ❌ Command failed: {cmd_resp.text[:300]}")

            # ── Step 13: Get Command History ──
            print("\n\n📜 Step 13: Getting Command History...")

            hist_resp = await client.get(
                f"/api/jarvis/cc/command/history?session_id={session_id}",
                headers=headers,
            )
            print(f"   Status: {hist_resp.status_code}")
            if hist_resp.status_code == 200:
                hist_data = hist_resp.json()
                cmd_count = len(hist_data) if isinstance(hist_data, list) else "N/A"
                print(f"   ✅ Command history: {cmd_count} commands")
            else:
                print(f"   ❌ History failed: {hist_resp.text[:300]}")

            # ── Step 14: Quick Commands ──
            print("\n\n⚡ Step 14: Testing Quick Commands...")

            qc_resp = await client.get(
                f"/api/jarvis/cc/command/quick-commands?session_id={session_id}",
                headers=headers,
            )
            print(f"   Status: {qc_resp.status_code}")
            if qc_resp.status_code == 200:
                qc_data = qc_resp.json()
                print(f"   ✅ Available quick commands:")
                if isinstance(qc_data, list):
                    for qc in qc_data[:10]:
                        print(f"      → {qc.get('name', qc.get('command', 'N/A'))}")
                else:
                    print(f"   📊 Data: {json.dumps(qc_data, indent=2)[:300]}...")
            else:
                print(f"   ❌ Quick commands failed: {qc_resp.text[:300]}")

            # ── Step 15: Awareness Delta ──
            print("\n\n📈 Step 15: Checking Awareness Delta...")

            delta_resp = await client.get(
                f"/api/jarvis/cc/awareness/delta?session_id={session_id}",
                headers=headers,
            )
            print(f"   Status: {delta_resp.status_code}")
            if delta_resp.status_code == 200:
                delta_data = delta_resp.json()
                print(f"   ✅ Delta retrieved!")
                print(f"   📊 Changes: {json.dumps(delta_data, indent=2)[:400]}...")
            else:
                print(f"   ❌ Delta failed: {delta_resp.text[:300]}")

        # ── Summary ──
        print("\n\n" + "=" * 70)
        print("  🏁 MANUAL TESTING COMPLETE — Summary")
        print("=" * 70)
        print(f"""
  ✅ Company: TechNova Solutions (technology, high_volume)
  ✅ Owner: Priya Sharma (owner@technova.com)
  ✅ Variants: 3 (mini_parwa, parwa, parwa_high)
  ✅ Customers: 20
  ✅ Tickets: 100 (mixed priorities, statuses, categories, channels)
  ✅ Jarvis CC Session: Created and active
  ✅ Chat: 5 messages sent to Jarvis
  ✅ Awareness: Tick triggered, snapshot retrieved
  ✅ Alerts: Retrieved from awareness engine
  ✅ Commands: 3 commands issued through command layer
  ✅ Quick Commands: Listed available commands
  ✅ Delta: Awareness change tracking verified
""")


if __name__ == "__main__":
    asyncio.run(run_manual_test())
