#!/usr/bin/env python3
"""
Create Real Test Ticket + Escalation for "Discuss with Jarvis" Flow Test
"""

import psycopg2
import json
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

# Database connection
DB_USER = "postgres.fmpibdauppnzfisodkhp"
DB_PASSWORD = "Durgamaa@754"
DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

encoded_password = quote_plus(DB_PASSWORD)
conn_str = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print("=" * 80)
print("CREATING REAL TEST TICKET FOR ESCALATION FLOW DEMO")
print("=" * 80)

try:
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    print("✅ Connected to Supabase!")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

now = datetime.now(timezone.utc)

# Get existing company and customer (from our previous test or create new ones)
test_company_id = f"comp_{uuid.uuid4().hex[:12]}"
test_customer_id = f"cust_{uuid.uuid4().hex[:12]}"
ticket_id = f"tick_{uuid.uuid4().hex[:12]}"

try:
    # 1. Create Test Company
    print("\n📁 Creating test company...")
    cur.execute("""
        INSERT INTO companies (id, name, industry, subscription_tier, subscription_status, mode, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (test_company_id, "Acme Corporation", "Technology", "enterprise", "active", "live", now, now))
    
    # 2. Create Test Customer  
    print("👤 Creating test customer...")
    cur.execute("""
        INSERT INTO customers (id, company_id, name, email, phone, metadata_json, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (test_customer_id, test_company_id, "John Doe", "john.doe@acme-corp.com", "+1-555-9999",
          json.dumps({"tier": "enterprise", "vip": True}), now, now))
    
    # 3. Create Ticket with ESCALATION status
    print("🎫 Creating escalated ticket...")
    cur.execute("""
        INSERT INTO tickets (
            id, company_id, customer_id, channel, status, subject, priority,
            category, awaiting_human, frozen, is_spam, reopen_count,
            escalation_level, sla_breached, awaiting_client,
            classification_intent, classification_type,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        ticket_id,                    # id
        test_company_id,              # company_id
        test_customer_id,             # customer_id
        "email",                      # channel
        "open",                       # status
        "URGENT: Refund request for $500 Enterprise plan - Customer threatening chargeback",  # subject
        "high",                       # priority
        "refund",                     # category
        True,                         # awaiting_human = TRUE (this triggers escalation!)
        False,                        # frozen
        False,                        # is_spam
        0,                            # reopen_count
        1,                            # escalation_level = 1 (escalated!)
        False,                        # sla_breached
        False,                        # awaiting_client
        "refund_request",             # classification_intent
        "billing_dispute",            # classification_type
        now,                          # created_at
        now                           # updated_at
    ))
    
    # 4. Add initial message from customer
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    cur.execute("""
        INSERT INTO ticket_messages (id, ticket_id, company_id, role, content, channel, 
                                      is_internal, is_redacted, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (message_id, ticket_id, test_company_id, "user",
          "Hi, I purchased your Enterprise plan for $500 last week but the AI features are not working as advertised. "
          "I've tried contacting support 3 times with no resolution. I'm very frustrated and if this isn't resolved "
          "within 24 hours I will be filing a chargeback with my credit card company. This is unacceptable for an "
          "enterprise product. I expect immediate attention to this issue.",
          "email", False, False, now - timedelta(hours=2)))
    
    # 5. Add AI response showing why it escalated
    ai_message_id = f"msg_{uuid.uuid4().hex[:12]}"
    cur.execute("""
        INSERT INTO ticket_messages (id, ticket_id, company_id, role, content, channel,
                                      is_internal, is_redacted, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (ai_message_id, ticket_id, test_company_id, "assistant",
          "I understand your frustration with the Enterprise plan issues. However, this involves: \n\n"
          "1. A potential chargeback threat (legal/financial risk)\n"
          "2. A high-value enterprise customer ($500/mo)\n"
          "3. Multiple failed support attempts\n"
          "4. Product functionality dispute\n\n"
          "**⚠️ ESCALATING TO HUMAN AGENT**\n\n"
          "This requires human review due to:\n- Chargeback/legal sensitivity\n- VIP customer at churn risk\n- Complex refund policy interpretation needed",
          "email", False, False, now - timedelta(minutes=30)))
    
    conn.commit()
    
    print("\n" + "=" * 80)
    print("✅✅✅ TICKET CREATED & ESCALATED SUCCESSFULLY! ✅✅✅")
    print("=" * 80)
    
    print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│                    🎫 TEST TICKET CREATED                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Ticket ID:         {ticket_id}                                │
│  Company ID:        {test_company_id}                              │
│  Customer ID:       {test_customer_id}                             │
│  Customer Name:     John Doe                                       │
│  Email:             john.doe@acme-corp.com                         │
│  Tier:              ENTERPRISE (VIP)                               │
│                                                                     │
│  Subject:           URGENT: Refund request for $500 Enterprise... │
│  Priority:          🔴 HIGH                                        │
│  Category:          💰 Refund                                       │
│  Status:            ⚠️ AWAITING_HUMAN (ESCALATED!)                │
│  Escalation Level:  1                                               │
│                                                                     │
│  Customer Message:                                                  │
│  "I purchased Enterprise plan for $500 but features not working.   │
│   Tried support 3 times. Will file chargeback in 24 hours."        │
│                                                                     │
│  Why Escalated:                                                     │
│  • Chargeback/Legal threat detected                                │
│  • High-value VIP customer at churn risk                           │
│  • Multiple failed support attempts                                │
│  • Complex refund policy needed                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
""")
    
    # Show how to access this ticket
    print("\n🔗 HOW TO TEST THE 'DISCUSS WITH JARVIS' FLOW:")
    print("-" * 80)
    print(f"""
1. Go to: http://localhost:3000/dashboard/escalations

2. Find the ticket with subject:
   "URGENT: Refund request for $500 Enterprise plan..."

3. Click the ORANGE button: 💬 "Discuss with Jarvis"

4. You'll be redirected to Jarvis Chat with URL:
   /dashboard/jarvis?ticket_id={ticket_id}
                   &subject=URGENT%3A+Refund+request...
                   &description=Customer+message...
                   &escalation_id={ticket_id}
                   &complexity=critical
                   &ticket_type=refund

5. Jarvis will auto-send:
   🎫 Ticket {ticket_id[:8].upper()} needs my attention
   
   Subject: URGENT: Refund request for $500 Enterprise plan...
   Customer asked: "I purchased your Enterprise plan..."
   
   Ticket Details:
   - Type: refund
   - Complexity: critical
   
   The AI variant paused on this ticket and needs my guidance.
   What do you recommend I should tell the AI to do?

6. Jarvis will respond with context-aware recommendations!
""")

except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

cur.close()
conn.close()

print("\n" + "=" * 80)
print("✅ DONE! Your escalation test ticket is ready.")
print("=" * 80)
