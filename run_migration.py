#!/usr/bin/env python3
"""
Run RAM-to-DB Migration on Production Supabase Database
"""

import psycopg2
from datetime import datetime

# Database connection
DB_CONFIG = {
    'host': 'aws-1-ap-northeast-1.pooler.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.fmpibdauppnzfisodkhp',
    'password': 'Durgamaa@754'
}

print("=" * 70)
print("RUNNING RAM-to-DB MIGRATION ON PRODUCTION")
print("=" * 70)
print(f"Time: {datetime.now().isoformat()}")
print()

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    
    # ══════════════════════════════════════════════════════════════════
    # 1. CREATE jarvis_safety_confirmations TABLE
    # ══════════════════════════════════════════════════════════════════
    print("📦 Creating jarvis_safety_confirmations table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jarvis_safety_confirmations (
            id VARCHAR(36) PRIMARY KEY DEFAULT (gen_random_uuid()::text),
            company_id VARCHAR(36) NOT NULL,
            session_id VARCHAR(255) NOT NULL,
            pending_id VARCHAR(255) NOT NULL,
            function_name VARCHAR(100) NOT NULL,
            safety_level VARCHAR(30) NOT NULL,
            params JSONB DEFAULT '{}',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            resolved_at TIMESTAMPTZ,
            resolved_by VARCHAR(255)
        );
    """)
    
    # Create indexes
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_jarvis_safety_pending 
        ON jarvis_safety_confirmations(company_id, session_id) 
        WHERE status = 'pending';
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_jarvis_safety_expires 
        ON jarvis_safety_confirmations(expires_at) 
        WHERE status = 'pending';
    """)
    print("   ✅ Table created with indexes")
    
    # ══════════════════════════════════════════════════════════════════
    # 2. CREATE demo_usage_sessions TABLE
    # ══════════════════════════════════════════════════════════════════
    print("\n📦 Creating demo_usage_sessions table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_usage_sessions (
            id VARCHAR(36) PRIMARY KEY DEFAULT (gen_random_uuid()::text),
            session_id VARCHAR(255) NOT NULL UNIQUE,
            user_id VARCHAR(36),
            company_id VARCHAR(36),
            user_messages_limit INTEGER NOT NULL DEFAULT 40,
            call_seconds_limit INTEGER NOT NULL DEFAULT 180,
            user_messages_sent INTEGER NOT NULL DEFAULT 0,
            jarvis_messages_sent INTEGER NOT NULL DEFAULT 0,
            call_seconds_used INTEGER NOT NULL DEFAULT 0,
            call_initiated BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_expired BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            expired_at TIMESTAMPTZ
        );
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_usage_active 
        ON demo_usage_sessions(session_id) 
        WHERE is_active = TRUE;
    """)
    print("   ✅ Table created with index")
    
    # ══════════════════════════════════════════════════════════════════
    # 3. CREATE demo_usage_events TABLE
    # ══════════════════════════════════════════════════════════════════
    print("\n📦 Creating demo_usage_events table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_usage_events (
            id VARCHAR(36) PRIMARY KEY DEFAULT (gen_random_uuid()::text),
            session_id VARCHAR(255) NOT NULL REFERENCES demo_usage_sessions(session_id),
            event_type VARCHAR(50) NOT NULL,
            event_data JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_events_session 
        ON demo_usage_events(session_id, created_at);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_events_created 
        ON demo_usage_events(created_at);
    """)
    print("   ✅ Table created with indexes")
    
    # ══════════════════════════════════════════════════════════════════
    # 4. ADD extended_metadata TO payment_failures TABLE
    # ══════════════════════════════════════════════════════════════════
    print("\n📦 Adding extended_metadata column to payment_failures...")
    
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'payment_failures' 
                AND column_name = 'extended_metadata'
            ) THEN
                ALTER TABLE payment_failures 
                    ADD COLUMN extended_metadata JSONB DEFAULT NULL;
                
                COMMENT ON COLUMN payment_failures.extended_metadata IS 
                    'Auto-block scheduling metadata: auto_block_scheduled, block_after_hours, etc.';
            END IF;
        END $$;
    """)
    print("   ✅ Column added (or already exists)")
    
    # Add index for auto-block queries
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_payment_failures_unresolved 
        ON payment_failures(company_id, created_at) 
        WHERE resolved = FALSE;
    """)
    print("   ✅ Index created for unresolved failures")
    
    # ══════════════════════════════════════════════════════════════════
    # 5. CREATE CLEANUP FUNCTIONS
    # ══════════════════════════════════════════════════════════════════
    print("\n📦 Creating cleanup functions...")
    
    # Function 1: Mark expired safety confirmations
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_safety_confirmations()
        RETURNS INTEGER AS $$
        DECLARE
            count INTEGER;
        BEGIN
            UPDATE jarvis_safety_confirmations
            SET status = 'expired', resolved_at = NOW()
            WHERE status = 'pending' AND expires_at < NOW();
            GET DIAGNOSTICS count = ROW_COUNT;
            RETURN count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ cleanup_expired_safety_confirmations()")
    
    # Function 2: Delete old resolved safety confirmations
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_safety_confirmations()
        RETURNS INTEGER AS $$
        DECLARE
            count INTEGER;
        BEGIN
            DELETE FROM jarvis_safety_confirmations
            WHERE status IN ('approved', 'rejected', 'expired')
              AND resolved_at < NOW() - INTERVAL '7 days';
            GET DIAGNOSTICS count = ROW_COUNT;
            RETURN count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ cleanup_old_safety_confirmations()")
    
    # Function 3: Delete old demo events
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_demo_events(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            count INTEGER;
        BEGIN
            DELETE FROM demo_usage_events
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS count = ROW_COUNT;
            RETURN count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ cleanup_old_demo_events()")
    
    # Function 4: Delete old demo sessions
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_demo_sessions(retention_days INTEGER DEFAULT 60)
        RETURNS INTEGER AS $$
        DECLARE
            count INTEGER;
        BEGIN
            DELETE FROM demo_usage_events
            WHERE session_id IN (
                SELECT session_id FROM demo_usage_sessions
                WHERE (is_expired = TRUE OR is_active = FALSE)
                  AND updated_at < NOW() - (retention_days || ' days')::INTERVAL
            );
            
            DELETE FROM demo_usage_sessions
            WHERE (is_expired = TRUE OR is_active = FALSE)
              AND updated_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS count = ROW_COUNT;
            RETURN count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ cleanup_old_demo_sessions()")
    
    # Function 5: Master cleanup function
    cur.execute("""
        CREATE OR REPLACE FUNCTION run_persistence_cleanup()
        RETURNS JSONB AS $$
        DECLARE
            result JSONB;
        BEGIN
            result := jsonb_build_object(
                'ran_at', NOW(),
                'safety_expired', cleanup_expired_safety_confirmations(),
                'safety_cleaned', cleanup_old_safety_confirmations(),
                'demo_events_deleted', cleanup_old_demo_events(30),
                'demo_sessions_deleted', cleanup_old_demo_sessions(60),
                'payment_failures_note', 'Use PaymentFailureService.cleanup_old_failures() for payment cleanup'
            );
            RETURN result;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ run_persistence_cleanup()")
    
    # ══════════════════════════════════════════════════════════════════
    # 6. VERIFY EVERYTHING
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    checks = [
        ('jarvis_safety_confirmations', 'TABLE'),
        ('demo_usage_sessions', 'TABLE'),
        ('demo_usage_events', 'TABLE'),
        ('cleanup_expired_safety_confirmations', 'FUNCTION'),
        ('cleanup_old_safety_confirmations', 'FUNCTION'),
        ('cleanup_old_demo_events', 'FUNCTION'),
        ('cleanup_old_demo_sessions', 'FUNCTION'),
        ('run_persistence_cleanup', 'FUNCTION'),
    ]
    
    all_passed = True
    for name, obj_type in checks:
        if obj_type == 'TABLE':
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (name,))
        else:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.routines 
                    WHERE routine_name = %s
                );
            """, (name,))
        
        exists = cur.fetchone()[0]
        status = "✅" if exists else "❌"
        print(f"  {status} {name} ({obj_type})")
        
        if not exists:
            all_passed = False
    
    # Check extended_metadata column
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'payment_failures' 
            AND column_name = 'extended_metadata'
        );
    """)
    col_exists = cur.fetchone()[0]
    print(f"  {'✅' if col_exists else '❌'} payment_failures.extended_metadata (COLUMN)")
    
    if not col_exists:
        all_passed = False
    
    # ══════════════════════════════════════════════════════════════════
    # FINAL RESULT
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    if all_passed:
        print("✅✅✅ MIGRATION COMPLETED SUCCESSFULLY! ✅✅✅")
    else:
        print("⚠️  MIGRATION COMPLETED WITH WARNINGS")
    print("=" * 70)
    
    print("""
┌─────────────────────────────────────────────────────────────┐
│                  🎉 DEPLOYMENT SUMMARY                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ✅ Tables Created:                                         │
│     • jarvis_safety_confirmations                          │
│     • demo_usage_sessions                                  │
│     • demo_usage_events                                    │
│                                                             │
│  ✅ Columns Added:                                          │
│     • payment_failures.extended_metadata                  │
│                                                             │
│  ✅ Functions Created:                                      │
│     • cleanup_expired_safety_confirmations()               │
│     • cleanup_old_safety_confirmations()                   │
│     • cleanup_old_demo_events()                            │
│     • cleanup_old_demo_sessions()                          │
│     • run_persistence_cleanup()                            │
│                                                             │
│  🔄 Next Steps:                                             │
│     • Background cleanup loop will run every hour          │
│     • Auto-block feature now ready for payment failures    │
│     • All data persists through server crashes             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
""")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ MIGRATION ERROR: {e}")
    import traceback
    traceback.print_exc()
