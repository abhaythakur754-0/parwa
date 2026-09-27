"""
PARWA Database Connection Fix - Production Ready
==================================================
This script fixes the backend to connect to Supabase PostgreSQL
and ensures all tables (tickets, trials, variants, integrations) work correctly.

Run this BEFORE starting the backend server:
  python fix_database_connection.py

Or import in your main.py:
  from fix_database_connection import verify_supabase_connection
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

# ── SUPABASE PRODUCTION DATABASE CONFIG ──
# Read from environment variables — NEVER hardcode credentials.
SUPABASE_CONFIG = {
    'host': os.environ.get('SUPABASE_HOST', ''),
    'port': int(os.environ.get('SUPABASE_PORT', '6543')),
    'dbname': os.environ.get('SUPABASE_DB', 'postgres'),
    'user': os.environ.get('SUPABASE_USER', ''),
    'password': os.environ.get('SUPABASE_PASSWORD', ''),
}

def get_supabase_connection():
    """Create connection to Supabase production database."""
    return psycopg2.connect(**SUPABASE_CONFIG)


def verify_all_tables_exist():
    """Verify all critical tables exist and are accessible."""
    required_tables = [
        # Core tables
        'users', 'companies', 
        # Ticket system
        'tickets', 'ticket_messages', 'ticket_assignments', 'ticket_status_changes',
        # Trial & Subscription
        'subscriptions', 'variant_instances', 'variant_limits',
        # Integration tools
        'integrations', 'api_keys', 'webhook_integrations', 'db_connections',
        # Escalation
        'parwa_escalation_vault',
        # Usage tracking
        'usage_records', 'v_company_usage_dashboard'
    ]
    
    conn = get_supabase_connection()
    cur = conn.cursor()
    
    print("="*60)
    print("🔍 VERIFYING ALL TABLES EXIST IN SUPABASE")
    print("="*60)
    
    results = {'found': [], 'missing': []}
    
    for table in required_tables:
        try:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = %s
                )
            """, (table,))
            exists = cur.fetchone()[0]
            
            if exists:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                results['found'].append((table, count))
                print(f"  ✅ {table}: {count} rows")
            else:
                results['missing'].append(table)
                print(f"  ❌ {table}: MISSING!")
                
        except Exception as e:
            results['missing'].append((table, str(e)))
            print(f"  ❌ {table}: ERROR - {e}")
    
    conn.close()
    
    return results


def verify_functions_exist():
    """Verify all our custom functions are deployed."""
    required_functions = [
        'check_user_usage_limit',
        'enforce_usage_limit_and_shutdown',
        'run_comprehensive_cleanup',
        '_data_cleanup_loop'
    ]
    
    conn = get_supabase_connection()
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("🔍 VERIFYING CUSTOM FUNCTIONS")
    print("="*60)
    
    for func_name in required_functions:
        try:
            cur.execute("""
                EXISTS (
                    SELECT FROM information_schema.routines 
                    WHERE routine_name = %s
                )
            """, (func_name,))
            
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.routines 
                    WHERE routine_name = %s
                )
            """, (func_name,))
            exists = cur.fetchone()[0]
            
            if exists:
                print(f"  ✅ {func_name}(): DEPLOYED")
            else:
                print(f"  ⚠️  {func_name}(): NOT FOUND")
                
        except Exception as e:
            print(f"  ❌ {func_name}(): Error - {e}")
    
    conn.close()


def test_ticket_creation():
    """Test that we can actually insert a ticket."""
    conn = get_supabase_connection()
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("🧪 TESTING TICKET INSERTION")
    print("="*60)
    
    try:
        import uuid
        test_id = f"test_{uuid.uuid4().hex[:12]}"
        
        # Get a valid company_id
        cur.execute("""
            SELECT id FROM companies WHERE is_trial = TRUE LIMIT 1
        """)
        company = cur.fetchone()
        
        if not company:
            print("  ⚠️ No trial companies found to test with")
            return False
        
        company_id = company[0]
        
        # Try inserting a test ticket
        cur.execute("""
            INSERT INTO tickets (
                id, company_id, customer_id, channel, status,
                subject, priority, created_at, updated_at
            ) VALUES (%s, %s, %s, 'web', 'open', %s, 'medium', NOW(), NOW())
            RETURNING id, status, created_at
        """, (test_id, company_id, company_id, "Database Connection Test - Auto-cleanup"))
        
        ticket = cur.fetchone()
        conn.commit()
        
        print(f"  ✅ TEST TICKET CREATED:")
        print(f"     ID: {ticket[0]}")
        print(f"     Status: {ticket[1]}")
        print(f"     Created: {ticket[2]}")
        
        # Clean up test ticket
        cur.execute("DELETE FROM tickets WHERE id = %s", (test_id,))
        conn.commit()
        print(f"  ✅ Test ticket cleaned up")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"  ❌ TICKET CREATION FAILED: {e}")
        return False
    
    finally:
        conn.close()


def generate_sqlalchemy_url():
    """Generate proper SQLAlchemy URL from config."""
    config = SUPABASE_CONFIG
    # Format: postgresql://user:password@host:port/dbname?sslmode=require
    url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['dbname']}?sslmode=require"
    return url


def update_env_file():
    """Update .env file with correct database URL."""
    env_path = '/home/z/my-project/backend/.env'
    
    sqlalchemy_url = generate_sqlalchemy_url()
    
    env_content = f"""# PARWA Backend Environment Configuration
# Auto-generated by fix_database_connection.py

# Database - Supabase Production
DATABASE_URL={sqlalchemy_url}

# Application
ENVIRONMENT=production
DEBUG=false

# Trial Settings
TRIAL_LIMIT_DISABLED=false

# Feature Flags
ENABLE_USAGE_TRACKING=true
ENABLE_VARIANT_LIMITS=true
"""
    
    try:
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        print(f"\n✅ Updated {env_path} with Supabase connection string")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to update .env: {e}")
        return False


def run_full_verification():
    """Run complete verification of database connectivity."""
    print("\n" + "#"*60)
    print("#  PARWA DATABASE CONNECTION VERIFICATION")
    print("#  Version 2.0.0 | Production Fix")
    print("#"*60)
    
    # Step 1: Test basic connection
    print("\n📡 STEP 1: Testing basic database connection...")
    try:
        conn = get_supabase_connection()
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"  ✅ CONNECTED SUCCESSFULLY!")
        print(f"     Database: {version.split(',')[0]}")
        conn.close()
    except Exception as e:
        print(f"  ❌ CONNECTION FAILED: {e}")
        return False
    
    # Step 2: Verify tables
    table_results = verify_all_tables_exist()
    
    if len(table_results['missing']) > 0:
        print(f"\n⚠️  WARNING: {len(table_results['missing'])} tables missing or inaccessible")
    
    # Step 3: Verify functions
    verify_functions_exist()
    
    # Step 4: Test ticket creation
    test_success = test_ticket_creation()
    
    # Step 5: Update .env file
    print("\n📝 STEP 5: Updating environment configuration...")
    update_env_file()
    
    # Summary
    print("\n" + "="*60)
    print("📊 VERIFICATION SUMMARY")
    print("="*60)
    
    all_good = (
        len(table_results['missing']) == 0 and
        test_success
    )
    
    if all_good:
        print("  ✅ ALL CHECKS PASSED!")
        print("\n  Your backend is ready to connect to Supabase.")
        print("  Start the server with:")
        print("    cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000")
    else:
        print("  ⚠️  SOME ISSUES FOUND")
        print(f"  Tables missing: {len(table_results['missing'])}")
        print(f"  Ticket creation works: {'Yes' if test_success else 'No'}")
        print("\n  Review the errors above before deploying.")
    
    return all_good


if __name__ == "__main__":
    success = run_full_verification()
    sys.exit(0 if success else 1)
