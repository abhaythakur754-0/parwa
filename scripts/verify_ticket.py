#!/usr/bin/env python3
"""Verify the escalated test ticket exists in database"""

import psycopg2
from urllib.parse import quote_plus

DB_USER = "postgres.fmpibdauppnzfisodkhp"
DB_PASSWORD = "Durgamaa@754"
DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

encoded_password = quote_plus(DB_PASSWORD)
conn_str = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

conn = psycopg2.connect(conn_str)
cur = conn.cursor()

print("=" * 80)
print("VERIFYING ESCALATED TICKET IN DATABASE")
print("=" * 80)

# Query the ticket we just created
cur.execute("""
    SELECT id, company_id, customer_id, subject, status, priority, category,
           awaiting_human, escalation_level, created_at
    FROM tickets 
    WHERE id LIKE 'tick_15bbfa52ada3'
""")

ticket = cur.fetchone()
if ticket:
    print(f"""
✅ TICKET FOUND IN DATABASE!

┌─────────────────────────────────────────────────────────────┐
│  Ticket ID:        {ticket[0]}                    
│  Company ID:       {ticket[1]}                      
│  Customer ID:      {ticket[2]}                      
│  Subject:          {ticket[3][:50]}...             
│  Status:           {ticket[4]}                      
│  Priority:         {ticket[5]}                       
│  Category:         {ticket[6]}                     
│  Awaiting Human:   {ticket[7]}                   
│  Escalation Level: {ticket[8]}                        
│  Created At:       {ticket[9]}                      
└─────────────────────────────────────────────────────────────┘

⚠️  ESCALATION STATUS: {'✅ ACTIVE - Ready for "Discuss with Jarvis"' if ticket[7] else '❌ NOT ESCALATED'}
""")
    
    # Get messages for this ticket
    print("\n📨 TICKET MESSAGES:")
    print("-" * 80)
    cur.execute("""
        SELECT role, LEFT(content, 100) as content_preview, created_at
        FROM ticket_messages 
        WHERE ticket_id = %s 
        ORDER BY created_at ASC
    """, (ticket[0],))
    
    messages = cur.fetchall()
    for i, (role, content, ts) in enumerate(messages, 1):
        icon = "👤" if role == "user" else "🤖"
        print(f"\n  {icon} Message {i} ({role.upper()}):")
        print(f"     \"{content}...\"")
        print(f"     Time: {ts}")
else:
    print("❌ Ticket not found!")

cur.close()
conn.close()
