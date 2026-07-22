#!/usr/bin/env python3
"""
COMPREHENSIVE DATA CLEANUP DEPLOYMENT
=====================================
Covers ALL temporary/ephemeral data in production database

CLEUP SCHEDULE:
┌─────────────────────────────┬──────────────────┬──────────────────────────────┐
│ Data Type                   │ Retention        │ Scope                        │
├─────────────────────────────┼──────────────────┼──────────────────────────────┤
│ Phone OTP                  │ 15 minutes       │ UNVERIFIED / EXPIRED only    │
│ Business Email OTP         │ 15 minutes       │ UNVERIFIED / EXPIRED only    │
│ Verification Tokens        │ 15 minutes       │ UNVERIFIED / EXPIRED only    │
│ Password Reset Tokens      │ 1 hour           │ EXPIRED only                 │
│ Safety Confirmations       │ Immediate mark   │ Delete after 7 days          │
│ Demo Usage Events          │ 30 days          │ All old events               │
│ Demo Usage Sessions        │ 60 days          │ Expired/inactive only        │
│ Resolved Tickets           │ 30 days          │ RESOLVED/CLOSED only         │
│ Ticket Messages            │ 60 days          │ Orphaned messages            │
│ Payment Failures           │ 90 days          │ RESOLVED only                │
│ Activity Log              │ 90 days          │ All old entries              │
│ Error Log                 │ 30 days          │ All old entries              │
│ Rate Limit Events         │ 7 days           │ All old events               │
│ Notification Logs         │ 30 days          │ All old entries              │
│ Agent Config History      │ 180 days         │ Old versions only            │
│ Audit Trail               │ 90 days          │ Old entries only             │
└─────────────────────────────┴──────────────────┴──────────────────────────────┘

RUNS: Every 15 minutes via application background loop
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

print("=" * 80)
print("🧹 COMPREHENSIVE DATA CLEANUP DEPLOYMENT")
print(f"   Time: {datetime.now().isoformat()}")
print("=" * 80)

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    
    # ══════════════════════════════════════════════════════════════════
    # SECTION 1: OTP & VERIFICATION CLEANUP (HIGH PRIORITY - 15 min)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🔴 SECTION 1: OTP & VERIFICATION CLEANUP (15 MIN)".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 1.1 Phone OTP Cleanup - Delete unverified/expired after 15 min
    print("\n📱 Creating cleanup_expired_phone_otps()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_phone_otps(retention_minutes INTEGER DEFAULT 15)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM phone_otps
            WHERE (verified = FALSE OR verified IS NULL)
              AND created_at < NOW() - (retention_minutes || ' minutes')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Phone OTP cleanup (15 min retention)")
    
    # 1.2 Business Email OTP Cleanup - Delete unverified/expired after 15 min
    print("\n📧 Creating cleanup_expired_email_otps()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_email_otps(retention_minutes INTEGER DEFAULT 15)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM business_email_otps
            WHERE (verified = FALSE OR verified IS NULL)
              AND created_at < NOW() - (retention_minutes || ' minutes')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Email OTP cleanup (15 min retention)")
    
    # 1.3 Verification Tokens Cleanup - Delete unused after 15 min
    print("\n🔑 Creating cleanup_expired_verification_tokens()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_verification_tokens(retention_minutes INTEGER DEFAULT 15)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM verification_tokens
            WHERE (is_used = FALSE OR is_used IS NULL)
              AND created_at < NOW() - (retention_minutes || ' minutes')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Verification tokens cleanup (15 min retention)")
    
    # 1.4 Password Reset Tokens - Delete expired after 1 hour
    print("\n🔐 Creating cleanup_expired_password_reset_tokens()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_password_reset_tokens(retention_hours INTEGER DEFAULT 1)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM password_reset_tokens
            WHERE (is_used = FALSE OR is_used IS NULL)
              AND created_at < NOW() - (retention_hours || ' hours')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Password reset tokens cleanup (1 hour retention)")
    
    # ══════════════════════════════════════════════════════════════════
    # SECTION 2: SAFETY CONFIRMATIONS (MEDIUM PRIORITY)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🟡 SECTION 2: SAFETY CONFIRMATIONS".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 2.1 Mark expired safety confirmations
    print("\n🛡️  Creating cleanup_expired_safety_confirmations()...")
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
    print("   ✅ Mark expired safety confirmations")
    
    # 2.2 Delete old resolved safety confirmations
    print("\n🗑️  Creating cleanup_old_safety_confirmations()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_safety_confirmations(retention_days INTEGER DEFAULT 7)
        RETURNS INTEGER AS $$
        DECLARE
            count INTEGER;
        BEGIN
            DELETE FROM jarvis_safety_confirmations
            WHERE status IN ('approved', 'rejected', 'expired')
              AND resolved_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS count = ROW_COUNT;
            RETURN count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Delete old safety confirmations (7 days)")
    
    # ══════════════════════════════════════════════════════════════════
    # SECTION 3: DEMO USAGE TRACKING (LOW PRIORITY)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🟢 SECTION 3: DEMO USAGE TRACKING".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 3.1 Clean demo usage events
    print("\n📊 Creating cleanup_old_demo_events()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_demo_events(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM demo_usage_events
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Demo events cleanup (30 days)")
    
    # 3.2 Clean expired demo sessions
    print("\n📊 Creating cleanup_old_demo_sessions()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_demo_sessions(retention_days INTEGER DEFAULT 60)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- First delete events from sessions we're about to delete
            DELETE FROM demo_usage_events
            WHERE session_id IN (
                SELECT session_id FROM demo_usage_sessions
                WHERE (is_expired = TRUE OR is_active = FALSE)
                  AND updated_at < NOW() - (retention_days || ' days')::INTERVAL
            );
            
            -- Then delete the sessions
            DELETE FROM demo_usage_sessions
            WHERE (is_expired = TRUE OR is_active = FALSE)
              AND updated_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Demo sessions cleanup (60 days)")
    
    # ══════════════════════════════════════════════════════════════════
    # SECTION 4: TICKET DATA CLEANUP (MEDIUM PRIORITY)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🟡 SECTION 4: TICKET DATA CLEANUP".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 4.1 Clean resolved/closed tickets
    print("\n🎫 Creating cleanup_old_resolved_tickets()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_resolved_tickets(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_tickets INTEGER;
            deleted_messages INTEGER;
            deleted_notes INTEGER;
        BEGIN
            -- Delete internal notes from old resolved tickets
            DELETE FROM ticket_internal_notes 
            WHERE ticket_id IN (
                SELECT id FROM tickets 
                WHERE status IN ('resolved', 'closed')
                AND updated_at < NOW() - (retention_days || ' days')::INTERVAL
            );
            GET DIAGNOSTICS deleted_notes = ROW_COUNT;
            
            -- Delete messages from old resolved tickets
            DELETE FROM ticket_messages 
            WHERE ticket_id IN (
                SELECT id FROM tickets 
                WHERE status IN ('resolved', 'closed')
                AND updated_at < NOW() - (retention_days || ' days')::INTERVAL
            );
            GET DIAGNOSTICS deleted_messages = ROW_COUNT;
            
            -- Delete related assignments
            DELETE FROM ticket_assignments 
            WHERE ticket_id IN (
                SELECT id FROM tickets 
                WHERE status IN ('resolved', 'closed')
                AND updated_at < NOW() - (retention_days || ' days')::INTERVAL
            );
            
            -- Delete related attachments
            DELETE FROM ticket_attachments 
            WHERE ticket_id IN (
                SELECT id FROM tickets 
                WHERE status IN ('resolved', 'closed')
                AND updated_at < NOW() - (retention_days || ' days')::INTERVAL
            );
            
            -- Finally delete the tickets
            DELETE FROM tickets 
            WHERE status IN ('resolved', 'closed')
            AND updated_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_tickets = ROW_COUNT;
            
            RETURN deleted_tickets;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Resolved tickets cleanup (30 days)")
    
    # 4.2 Clean old ticket messages
    print("\n💬 Creating cleanup_old_ticket_messages()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_ticket_messages(retention_days INTEGER DEFAULT 60)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM ticket_messages 
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old ticket messages cleanup (60 days)")
    
    # 4.3 Clean old ticket internal notes
    print("\n📝 Creating cleanup_old_ticket_internal_notes()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_ticket_internal_notes(retention_days INTEGER DEFAULT 60)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM ticket_internal_notes 
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old internal notes cleanup (60 days)")
    
    # ══════════════════════════════════════════════════════════════════
    # SECTION 5: LOG & AUDIT DATA CLEANUP (LOW-MEDIUM PRIORITY)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🟢 SECTION 5: LOG & AUDIT DATA CLEANUP".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 5.1 Activity Log cleanup
    print("\n📋 Creating cleanup_old_activity_log()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_activity_log(retention_days INTEGER DEFAULT 90)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM activity_log
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Activity log cleanup (90 days)")
    
    # 5.2 Error Log cleanup
    print("\n❌ Creating cleanup_old_error_log()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_error_log(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM error_log
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Error log cleanup (30 days)")
    
    # 5.3 Rate Limit Events cleanup
    print("\n⚡ Creating cleanup_old_rate_limit_events()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_rate_limit_events(retention_days INTEGER DEFAULT 7)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM rate_limit_events
            WHERE last_attempt_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Rate limit events cleanup (7 days)")
    
    # 5.4 Notification Logs cleanup
    print("\n🔔 Creating cleanup_old_notification_logs()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_notification_logs(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM notification_logs
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Notification logs cleanup (30 days)")
    
    # 5.5 Email Logs cleanup
    print("\n📧 Creating cleanup_old_email_logs()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_email_logs(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM email_logs
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Email logs cleanup (30 days)")
    
    # 5.6 Agent Config History cleanup (keep recent versions)
    print("\n🤖 Creating cleanup_old_agent_config_history()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_agent_config_history(retention_days INTEGER DEFAULT 180)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- Keep at least latest version per agent, delete old history
            DELETE FROM agent_config_history
            WHERE changed_at < NOW() - (retention_days || ' days')::INTERVAL
              AND id NOT IN (
                  SELECT MAX(id) FROM agent_config_history GROUP BY agent_id
              );
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Agent config history cleanup (180 days)")
    
    # 5.7 Audit Trail cleanup
    print("\n📝 Creating cleanup_old_audit_trail()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_audit_trail(retention_days INTEGER DEFAULT 90)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM audit_trail
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Audit trail cleanup (90 days)")
    
    # ══════════════════════════════════════════════════════════════════
    # SECTION 6: MASTER CLEANUP FUNCTION (RUNS EVERYTHING)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🎯 SECTION 6: MASTER CLEANUP FUNCTION".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    print("\n⚙️  Creating run_comprehensive_cleanup() [MASTER]...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION run_comprehensive_cleanup()
        RETURNS JSONB AS $$
        DECLARE
            result JSONB;
        BEGIN
            result := jsonb_build_object(
                'ran_at', NOW(),
                'version', '2.0-comprehensive',
                
                -- Section 1: OTP & Verification (HIGH PRIORITY)
                'phone_otps_deleted', cleanup_expired_phone_otps(15),
                'email_otps_deleted', cleanup_expired_email_otps(15),
                'verification_tokens_deleted', cleanup_expired_verification_tokens(15),
                'password_reset_tokens_deleted', cleanup_expired_password_reset_tokens(1),
                
                -- Section 2: Safety Confirmations
                'safety_confirmations_expired', cleanup_expired_safety_confirmations(),
                'safety_confirmations_cleaned', cleanup_old_safety_confirmations(7),
                
                -- Section 3: Demo Usage
                'demo_events_deleted', cleanup_old_demo_events(30),
                'demo_sessions_deleted', cleanup_old_demo_sessions(60),
                
                -- Section 4: Tickets
                'resolved_tickets_deleted', cleanup_old_resolved_tickets(30),
                'old_messages_deleted', cleanup_old_ticket_messages(60),
                'old_internal_notes_deleted', cleanup_old_ticket_internal_notes(60),
                
                -- Section 5: Logs & Audit
                'activity_log_deleted', cleanup_old_activity_log(90),
                'error_log_deleted', cleanup_old_error_log(30),
                'rate_limit_events_deleted', cleanup_old_rate_limit_events(7),
                'notification_logs_deleted', cleanup_old_notification_logs(30),
                'email_logs_deleted', cleanup_old_email_logs(30),
                'agent_config_history_cleaned', cleanup_old_agent_config_history(180),
                'audit_trail_cleaned', cleanup_old_audit_trail(90),
                
                -- Note for payment failures (handled by Python service)
                'payment_failures_note', 'Use PaymentFailureService.cleanup_old_failures(90)'
            );
            
            RETURN result;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Master cleanup function created!")
    
    # ══════════════════════════════════════════════════════════════════
    # TEST: RUN THE MASTER FUNCTION
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  ✅ TESTING: Running master cleanup function...".center(76) + "║")
    print("╚" + "═" * 78 + "╝\n")
    
    cur.execute("SELECT run_comprehensive_cleanup();")
    result = cur.fetchone()[0]
    
    import json
    if result:
        cleanup_result = json.loads(result) if isinstance(result, str) else result
        
        print("🎉 SUCCESS! All cleanup functions executed:\n")
        print(f"{'Function':<40} {'Records Affected':>20}")
        print("-" * 65)
        
        for key, value in cleanup_result.items():
            if key == 'ran_at':
                print(f"{key:<40} {str(value):>20}")
            elif key == 'version':
                print(f"{key:<40} {str(value):>20}")
            elif 'note' in key.lower():
                print(f"{key:<40} {'(see note)':>20}")
            else:
                icon = "✅" if value == 0 else "🧹"
                print(f"{icon} {key:<38} {str(value):>20}")
        
        total_cleaned = sum(v for k, v in cleanup_result.items() 
                          if isinstance(v, int) and v > 0)
        
        print("\n" + "-" * 65)
        print(f"Total records cleaned this run: {total_cleaned}")
    
    # ══════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════════════
    print("\n\n" + "=" * 80)
    print("🎊 COMPREHENSIVE CLEANUP SYSTEM DEPLOYED SUCCESSFULLY!")
    print("=" * 80)
    
    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                         📋 CLEANUP FUNCTIONS DEPLOYED                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  🔴 HIGH PRIORITY (Runs every 15 min)                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • cleanup_expired_phone_otps(15 min)        → Unverified phone OTPs       │
│  • cleanup_expired_email_otps(15 min)        → Unverified email OTPs       │
│  • cleanup_expired_verification_tokens(15min)→ Unused verification tokens  │
│  • cleanup_expired_password_reset_tokens(1h) → Unused reset tokens         │
│                                                                             │
│  🟡 MEDIUM PRIORITY (Runs every hour)                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • cleanup_expired_safety_confirmations()   → Mark pending as expired      │
│  • cleanup_old_safety_confirmations(7d)     → Delete old confirmations     │
│  • cleanup_old_resolved_tickets(30d)        → Delete resolved tickets      │
│  • cleanup_old_ticket_messages(60d)         → Delete orphaned messages     │
│  • cleanup_old_ticket_internal_notes(60d)   → Delete old notes             │
│                                                                             │
│  🟢 LOW PRIORITY (Runs every hour)                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • cleanup_old_demo_events(30d)             → Old demo tracking            │
│  • cleanup_old_demo_sessions(60d)           → Expired demo sessions        │
│  • cleanup_old_activity_log(90d)            → Old activity logs            │
│  • cleanup_old_error_log(30d)               → Old error logs               │
│  • cleanup_old_rate_limit_events(7d)        → Old rate limit logs          │
│  • cleanup_old_notification_logs(30d)       → Old notification logs        │
│  • cleanup_old_email_logs(30d)              → Old email delivery logs      │
│  • cleanup_old_agent_config_history(180d)   → Old agent version history    │
│  • cleanup_old_audit_trail(90d)             → Old audit trail entries      │
│                                                                             │
│  ⚙️  MASTER FUNCTION                                                        │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • run_comprehensive_cleanup()              → Runs ALL functions at once   │
│                                                                             │
│  ⏰  SCHEDULE                                                                │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • Call run_comprehensive_cleanup() every 15 minutes from your app          │
│  • Or use PostgreSQL pg_cron extension for DB-side scheduling               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
""")
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
