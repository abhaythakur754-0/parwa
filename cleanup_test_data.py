#!/usr/bin/env python3
"""
CLEANUP: Remove Test Data Created During Testing
- Delete test user: test_ram_migration@parwa.buzz
- Delete test company: TestCompanyRAM-DB
- Delete test ticket: TKT-724F41E6 (RAM-to-DB Migration test)
"""

import psycopg2
from datetime import datetime

DB_CONFIG = {
    'host': 'aws-1-ap-northeast-1.pooler.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.fmpibdauppnzfisodkhp',
    'password': 'Durgamaa@754'
}

print("=" * 70)
print("⚠️  CLEANING UP TEST DATA FROM PRODUCTION")
print("=" * 70)
print(f"Time: {datetime.now().isoformat()}")
print()

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    
    # ══════════════════════════════════════════════════════════════════
    # 1. FIND AND DELETE TEST TICKET
    # ══════════════════════════════════════════════════════════════════
    print("🗑️  Looking for test ticket...")
    
    cur.execute("""
        SELECT id, subject, created_at 
        FROM tickets 
        WHERE subject ILIKE '%RAM-to-DB Migration%' 
           OR subject ILIKE '%Testing RAM%';
    """)
    
    test_tickets = cur.fetchall()
    
    if test_tickets:
        print(f"   Found {len(test_tickets)} test ticket(s):")
        for t in test_tickets:
            tid = t[0]
            print(f"      • ID: {tid[:20]}... | {t[1][:50]}")
            
            # Delete related data first (messages, notes, etc.)
            cur.execute("DELETE FROM ticket_messages WHERE ticket_id = %s;", (tid,))
            cur.execute("DELETE FROM ticket_internal_notes WHERE ticket_id = %s;", (tid,))
            cur.execute("DELETE FROM ticket_assignments WHERE ticket_id = %s;", (tid,))
            
            # Delete the ticket
            cur.execute("DELETE FROM tickets WHERE id = %s;", (tid,))
            print(f"      ✅ Deleted ticket {tid[:12]}...")
    else:
        print("   ✅ No test tickets found")
    
    # ══════════════════════════════════════════════════════════════════
    # 2. FIND AND DELETE TEST USER
    # ══════════════════════════════════════════════════════════════════
    print("\n👤 Looking for test user...")
    
    cur.execute("""
        SELECT id, email, full_name 
        FROM users 
        WHERE email = 'test_ram_migration@parwa.buzz'
           OR email LIKE '%test_ram%'
           OR full_name ILIKE '%Test RAM Migration%';
    """)
    
    test_users = cur.fetchall()
    
    if test_users:
        print(f"   Found {len(test_users)} test user(s):")
        for u in test_users:
            uid = u[0]
            print(f"      • ID: {uid[:20]}... | Email: {u[1]}")
            
            # Delete related data
            cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s;", (uid,))
            cur.execute("DELETE FROM notification_preferences WHERE user_id = %s;", (uid,))
            cur.execute("DELETE FROM mfa_secrets WHERE user_id = %s;", (uid,))
            
            # Delete user
            cur.execute("DELETE FROM users WHERE id = %s;", (uid,))
            print(f"      ✅ Deleted user {u[1]}")
    else:
        print("   ✅ No test users found")
    
    # ══════════════════════════════════════════════════════════════════
    # 3. FIND AND DELETE TEST COMPANY
    # ══════════════════════════════════════════════════════════════════
    print("\n🏢 Looking for test company...")
    
    cur.execute("""
        SELECT id, name 
        FROM companies 
        WHERE name ILIKE '%TestCompanyRAM%' 
           OR name ILIKE '%Test Company RAM%'
           OR name ILIKE '%RAM-DB%';
    """)
    
    test_companies = cur.fetchall()
    
    if test_companies:
        print(f"   Found {len(test_companies)} test company(ies):")
        for c in test_companies:
            cid = c[0]
            print(f"      • ID: {cid[:20]}... | Name: {c[1]}")
            
            # Delete related data
            cur.execute("DELETE FROM company_settings WHERE company_id = %s;", (cid,))
            cur.execute("DELETE FROM subscriptions WHERE company_id = %s;", (cid,))
            cur.execute("UPDATE users SET company_id = NULL WHERE company_id = %s;", (cid,))
            
            # Delete company
            cur.execute("DELETE FROM companies WHERE id = %s;", (cid,))
            print(f"      ✅ Deleted company {c[1]}")
    else:
        print("   ✅ No test companies found")
    
    # ══════════════════════════════════════════════════════════════════
    # 4. VERIFY CLEANUP
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("VERIFICATION: Confirming cleanup")
    print("=" * 70)
    
    # Check tickets
    cur.execute("SELECT COUNT(*) FROM tickets WHERE subject ILIKE '%RAM-to-DB Migration%';")
    remaining_tickets = cur.fetchone()[0]
    print(f"  Test tickets remaining: {remaining_tickets} {'✅ CLEAN' if remaining_tickets == 0 else '❌ STILL EXISTS'}")
    
    # Check users
    cur.execute("SELECT COUNT(*) FROM users WHERE email = 'test_ram_migration@parwa.buzz';")
    remaining_users = cur.fetchone()[0]
    print(f"  Test users remaining: {remaining_users} {'✅ CLEAN' if remaining_users == 0 else '❌ STILL EXISTS'}")
    
    # Check companies
    cur.execute("SELECT COUNT(*) FROM companies WHERE name ILIKE '%TestCompanyRAM%';")
    remaining_companies = cur.fetchone()[0]
    print(f"  Test companies remaining: {remaining_companies} {'✅ CLEAN' if remaining_companies == 0 else '❌ STILL EXISTS'}")
    
    if remaining_tickets == 0 and remaining_users == 0 and remaining_companies == 0:
        print("\n✅✅✅ ALL TEST DATA REMOVED FROM PRODUCTION ✅✅✅")
    else:
        print("\n⚠️  Some test data may remain - manual check needed")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ ERROR during cleanup: {e}")
    import traceback
    traceback.print_exc()
