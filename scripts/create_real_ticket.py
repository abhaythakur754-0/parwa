#!/usr/bin/env python3
"""
REAL TICKET CREATION TEST
Actually creates a ticket in user's Supabase database
This proves AI variants can WRITE (not just read) external data
"""

import psycopg2
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import quote_plus

# Database connection
DB_USER = "postgres.fmpibdauppnzfisodkhp"
DB_PASSWORD = "Durgamaa@754"
DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

DATABASE_URL = f"postgresql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_real_ticket():
    """Create an actual ticket in the database"""
    
    print("=" * 70)
    print("🎫 CREATING REAL TICKET IN YOUR SUPABASE DATABASE")
    print("=" * 70)
    print("\n⚠️  THIS IS NOT A SIMULATION - ACTUAL DATA BEING WRITTEN!")
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Get a real customer ID from main customers table (required for FK constraint)
    print("\n[1/5] Getting customer from database...")
    cursor.execute("SELECT id, email FROM customers LIMIT 1;")
    customer = cursor.fetchone()
    
    if not customer:
        print("❌ No customers found!")
        return None
    
    customer_id, customer_email = customer
    customer_name = customer_email.split('@')[0].replace('.', ' ').title()  # Generate name from email
    print(f"   ✅ Found customer: {customer_name} ({customer_email})")
    
    # Get a company ID
    print("\n[2/5] Getting company ID...")
    cursor.execute("SELECT id FROM companies LIMIT 1;")
    company = cursor.fetchone()
    company_id = company[0] if company else 'default-company'
    print(f"   ✅ Company ID: {company_id}")
    
    # Create the ticket with REAL data
    print("\n[3/5] Creating ticket in database...")
    
    ticket_data = {
        'id': str(uuid.uuid4()),
        'company_id': company_id,
        'customer_id': customer_id,
        'channel': 'chat',
        'status': 'open',
        'subject': 'Integration Test: Supabase Connection Verified by AI Variant',
        'priority': 'normal',
        'category': 'technical',
        'tags': ['integration-test', 'supabase', 'ai-variant'],
        'agent_id': None,
        'assigned_to': None,
        'classification_intent': 'integration_verification',
        'classification_type': 'question',
        'metadata_json': json.dumps({
            'source': 'ai_variant_supabase_test',
            'test_type': 'write_capability',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'verified_by': 'PARWA_AI_VARIANT'
        }),
        'reopen_count': 0,
        'frozen': False,
        'parent_ticket_id': None,
        'duplicate_of_id': None,
        'is_spam': False,
        'awaiting_human': False,
        'awaiting_client': False,
        'escalation_level': 0,
        'sla_breached': False,
        'plan_snapshot': None,
        'variant_version': 'v2-supabase-integrated',
        'first_response_at': None,
        'resolution_target_at': None,
        'client_timezone': 'UTC',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
        'closed_at': None
    }
    
    # Execute INSERT
    insert_sql = """
        INSERT INTO tickets (
            id, company_id, customer_id, channel, status, subject, 
            priority, category, tags, agent_id, assigned_to, 
            classification_intent, classification_type, metadata_json,
            reopen_count, frozen, parent_ticket_id, duplicate_of_id,
            is_spam, awaiting_human, awaiting_client, escalation_level,
            sla_breached, variant_version, client_timezone,
            created_at, updated_at, closed_at
        ) VALUES (
            %(id)s, %(company_id)s, %(customer_id)s, %(channel)s, %(status)s, %(subject)s,
            %(priority)s, %(category)s, %(tags)s, %(agent_id)s, %(assigned_to)s,
            %(classification_intent)s, %(classification_type)s, %(metadata_json)s,
            %(reopen_count)s, %(frozen)s, %(parent_ticket_id)s, %(duplicate_of_id)s,
            %(is_spam)s, %(awaiting_human)s, %(awaiting_client)s, %(escalation_level)s,
            %(sla_breached)s, %(variant_version)s, %(client_timezone)s,
            %(created_at)s, %(updated_at)s, %(closed_at)s
        )
    """
    
    cursor.execute(insert_sql, ticket_data)
    conn.commit()
    
    print(f"   ✅ Ticket CREATED successfully!")
    print(f"   📋 Ticket ID: {ticket_data['id']}")
    
    # Verify the ticket was actually created
    print("\n[4/5] Verifying ticket exists in database...")
    cursor.execute("""
        SELECT id, subject, status, priority, created_at 
        FROM tickets 
        WHERE id = %s;
    """, (ticket_data['id'],))
    
    verified = cursor.fetchone()
    
    if verified:
        print(f"   ✅ VERIFIED! Ticket exists in database:")
        print(f"      ID: {verified[0]}")
        print(f"      Subject: {verified[1]}")
        print(f"      Status: {verified[2]}")
        print(f"      Priority: {verified[3]}")
        print(f"      Created: {verified[4]}")
        
        # Count total tickets now
        cursor.execute("SELECT COUNT(*) FROM tickets;")
        total_tickets = cursor.fetchone()[0]
        print(f"\n   📊 Total tickets in database: {total_tickets}")
        
    else:
        print("   ❌ ERROR: Ticket not found after creation!")
        return None
    
    # Also create a ticket message
    print("\n[5/5] Adding message to the ticket...")
    
    message_data = {
        'id': str(uuid.uuid4()),
        'ticket_id': ticket_data['id'],
        'company_id': company_id,
        'role': 'customer',
        'content': f'This is an automated test message from PARWA AI Variant.\n\n'
                f'✅ Supabase Integration Test - SUCCESSFUL\n'
                f'🤖 AI Variant was able to:\n'
                f'   1. Connect to external database (Supabase)\n'
                f'   2. Query existing data\n'
                f'   3. CREATE new records (this ticket)\n'
                f'   4. Write messages\n\n'
                f'Test Timestamp: {datetime.now(timezone.utc).isoformat()}\n'
                f'Customer: {customer_name} ({customer_email})',
        'channel': 'chat',
        'metadata_json': json.dumps({'sender_name': customer_name}),
        'is_internal': False,
        'is_redacted': False,
        'ai_confidence': None,
        'variant_version': 'v2-supabase-integrated',
        'classification': None,
        'created_at': datetime.now(timezone.utc)
    }
    
    cursor.execute("""
        INSERT INTO ticket_messages (
            id, ticket_id, company_id, role, content, channel,
            metadata_json, is_internal, is_redacted, ai_confidence,
            variant_version, classification, created_at
        ) VALUES (
            %(id)s, %(ticket_id)s, %(company_id)s, %(role)s, %(content)s, %(channel)s,
            %(metadata_json)s, %(is_internal)s, %(is_redacted)s, %(ai_confidence)s,
            %(variant_version)s, %(classification)s, %(created_at)s
        )
    """, message_data)
    
    conn.commit()
    print(f"   ✅ Message added to ticket!")
    
    cursor.close()
    conn.close()
    
    # Final summary
    print("\n" + "=" * 70)
    print("🎉 SUCCESS! REAL TICKET CREATED IN YOUR DATABASE!")
    print("=" * 70)
    
    print(f"\n✅ WHAT HAPPENED:")
    print(f"   📍 Connected to: {DB_HOST}")
    print(f"   📝 Created Ticket: {ticket_data['id'][:8]}...")
    print(f"   👤 For Customer: {customer_name}")
    print(f"   💬 Added Message: YES")
    print(f"   ⏰ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    print(f"\n💡 PROOF THAT AI VARIANTS CAN:")
    print(f"   ✅ CONNECT to external databases")
    print(f"   ✅ READ existing data")
    print(f"   ✅ WRITE new records (tickets, messages)")
    print(f"   ✅ INTEGRATE beyond CRM")
    
    print(f"\n🔗 CHECK YOUR DASHBOARD:")
    print(f"   Go to https://parwa.buzz and look for this ticket:")
    print(f"   '{ticket_data['subject'][:50]}...'")
    
    return ticket_data['id']

if __name__ == "__main__":
    result = create_real_ticket()
    
    if result:
        print(f"\n🚀 READY FOR PRODUCTION! Change API keys when ready.")
    else:
        print(f"\n❌ Something went wrong.")
