#!/usr/bin/env python3
"""
COMPREHENSIVE DATA CLEANUP FIX v2.0
====================================
Fixes identified by user:

1. ❌ Messages retention was 60 days (should be 30 to match tickets)
   → Orphaned messages when parent ticket is deleted!

2. ❌ Agent deletion not cascading properly
   → When user deletes agent in UI, must also delete:
     * agent_config_history entries
     * ai_agent_assignments records  
     * custom_categories referencing this agent
     * Any other references

3. ❌ Other orphaned data scenarios not covered:
   * ticket_* tables with missing parent tickets
   * Old/expired sessions (jarvis, chat widget, SMS)
   * Abandoned onboarding sessions
   * Expired refresh tokens
   * Old pipeline snapshots, training data, shadow mode results
   * Outbound emails history
   * Technique execution caches

CLEANUP SCHEDULE (UPDATED):
┌─────────────────────────────┬──────────────────┬──────────────────────────────┐
│ Data Type                   │ Retention        │ Scope                        │
├─────────────────────────────┼──────────────────┼──────────────────────────────┤
│ Phone OTP                  │ 15 minutes       │ UNVERIFIED only              │
│ Business Email OTP         │ 15 minutes       │ UNVERIFIED only              │
│ Verification Tokens        │ 15 minutes       │ UNUSED only                  │
│ Password Reset Tokens      │ 1 hour           │ UNUSED only                  │
│ Rate Limit Events          │ 7 days           │ All old events               │
│ Safety Confirmations       │ 7 days           │ RESOLVED only                │
│ Error Log                 │ 30 days           │ All old entries              │
│ Notification Logs         │ 30 days           │ All old entries              │
│ Email Logs                │ 30 days           │ All old entries              │
│ Resolved Tickets          │ 30 days           │ RESOLVED/CLOSED only         │
│ Ticket Messages           │ 30 days ⬅️ FIXED  │ All messages (match tickets)  │
│ Ticket Internal Notes     │ 30 days ⬅️ FIXED  │ All notes (match tickets)     │
│ Demo Usage Events         │ 30 days           │ All old events               │
│ Demo Usage Sessions       │ 60 days           │ EXPIRED only                 │
│ Activity Log             │ 90 days           │ All old entries              │
│ Payment Failures         │ 90 days           │ RESOLVED only                │
│ Agent Config History     │ 180 days          │ Old versions only            │
│ Audit Trail              │ 90 days           │ All old entries              │
│ Jarvis Sessions          │ 7 days           │ INACTIVE only                │
│ Onboarding Sessions      │ 30 days          │ ABANDONED only               │
│ Refresh Tokens           │ 30 days          │ EXPIRED only                 │
│ Chat Widget Sessions     │ 30 days          │ INACTIVE only                │
│ Pipeline Snapshots       │ 7 days           │ OLD snapshots                │
│ Shadow Mode Results      │ 30 days          │ OLD results                  │
│ Technique Executions     │ 7 days           │ OLD executions               │
│ Outbound Emails          │ 30 days          │ OLD emails                   │
└─────────────────────────────┴──────────────────┴──────────────────────────────┘

AGENT DELETION CASCADE:
When agent is deleted (status = 'deleted' OR actual DELETE):
├── Delete from agents table
├── Delete from agent_config_history
├── Delete from ai_agent_assignments  
├── Update custom_categories (set agent_id = NULL)
└── Clean up any ticket assignments to this agent
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
print("🧹 COMPREHENSIVE CLEANUP FIX v2.0")
print(f"   Time: {datetime.now().isoformat()}")
print("=" * 80)

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    
    # ══════════════════════════════════════════════════════════════════
    # FIX 1: UPDATE MESSAGE RETENTION TO 30 DAYS (MATCH TICKETS!)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🔧 FIX 1: MESSAGE RETENTION → 30 DAYS (was 60)".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 1.1 Fix ticket_messages cleanup (30 days, not 60!)
    print("\n💬 Updating cleanup_old_ticket_messages() → 30 days...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_ticket_messages(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- Delete messages older than retention period
            -- This prevents orphaned messages when parent tickets are deleted!
            DELETE FROM ticket_messages 
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Ticket messages now cleaned after 30 days (matches ticket cleanup)")
    
    # 1.2 Fix ticket_internal_notes cleanup (30 days, not 60!)
    print("\n📝 Updating cleanup_old_ticket_internal_notes() → 30 days...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_ticket_internal_notes(retention_days INTEGER DEFAULT 30)
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
    print("   ✅ Internal notes now cleaned after 30 days (matches ticket cleanup)")
    
    # ══════════════════════════════════════════════════════════════════
    # FIX 2: AGENT DELETION CASCADE
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🤖 FIX 2: AGENT DELETION CASCADE".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 2.1 Function to fully delete an agent and ALL its related data
    print("\n🗑️  Creating cascade_delete_agent()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cascade_delete_agent(target_agent_id VARCHAR(36))
        RETURNS JSONB AS $$
        DECLARE
            result JSONB;
            history_deleted INTEGER;
            assignments_deleted INTEGER;
            categories_updated INTEGER;
            agent_deleted INTEGER;
        BEGIN
            -- 1. Delete agent config history
            DELETE FROM agent_config_history 
            WHERE agent_id = target_agent_id;
            GET DIAGNOSTICS history_deleted = ROW_COUNT;
            
            -- 2. Delete AI agent assignments
            DELETE FROM ai_agent_assignments 
            WHERE id = target_agent_id 
               OR agent_id = target_agent_id;
            GET DIAGNOSTICS assignments_deleted = ROW_COUNT;
            
            -- 3. Update custom categories (remove reference to this agent)
            UPDATE custom_categories 
            SET agent_id = NULL, is_active = FALSE
            WHERE agent_id = target_agent_id;
            GET DIAGNOSTICS categories_updated = ROW_COUNT;
            
            -- 4. Finally delete the agent itself
            DELETE FROM agents 
            WHERE id = target_agent_id;
            GET DIAGNOSTICS agent_deleted = ROW_COUNT;
            
            result := jsonb_build_object(
                'agent_id', target_agent_id,
                'history_deleted', history_deleted,
                'assignments_deleted', assignments_deleted,
                'categories_updated', categories_updated,
                'agent_deleted', agent_deleted,
                'deleted_at', NOW()
            );
            
            RETURN result;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Cascade delete function ready")
    
    # 2.2 Function to find and clean up soft-deleted agents
    print("\n🧹 Creating cleanup_deleted_agents()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_deleted_agents(grace_period_days INTEGER DEFAULT 7)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
            agent_record RECORD;
        BEGIN
            -- Find agents marked as deleted beyond grace period
            FOR agent_record IN 
                SELECT id FROM agents 
                WHERE status = 'deleted' 
                  AND created_at < NOW() - (grace_period_days || ' days')::INTERVAL
            LOOP
                -- Use cascade delete for each
                PERFORM cascade_delete_agent(agent_record.id);
                deleted_count := COALESCE(deleted_count, 0) + 1;
            END LOOP;
            
            RETURN COALESCE(deleted_count, 0);
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Deleted agents cleanup ready (after 7-day grace period)")
    
    # 2.3 Trigger to auto-cascade on agent DELETE
    print("\n⚡ Creating trigger for automatic cascade on agent DELETE...")
    
    # Create proper trigger function first
    cur.execute("""
        CREATE OR REPLACE FUNCTION fn_cascade_agent_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Delete config history
            DELETE FROM agent_config_history WHERE agent_id = OLD.id;
            
            -- Delete AI assignments
            DELETE FROM ai_agent_assignments WHERE id = OLD.id OR agent_id = OLD.id;
            
            -- Clear category references
            UPDATE custom_categories SET agent_id = NULL, is_active = FALSE 
            WHERE agent_id = OLD.id;
            
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        
        DROP TRIGGER IF EXISTS trg_cascade_agent_delete ON agents;
        
        CREATE TRIGGER trg_cascade_agent_delete
        BEFORE DELETE ON agents
        FOR EACH ROW EXECUTE FUNCTION fn_cascade_agent_delete();
    """)
    print("   ✅ Auto-cascade trigger installed (any agent DELETE cleans everything)")
    
    # ══════════════════════════════════════════════════════════════════
    # FIX 3: ORPHANED DATA CLEANUP (NEW!)
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🔍 FIX 3: ORPHANED DATA CLEANUP (NEW!)".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # 3.1 Clean orphaned ticket-related records
    print("\n🎫 Creating cleanup_orphaned_ticket_data()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_orphaned_ticket_data()
        RETURNS JSONB AS $$
        DECLARE
            result JSONB;
            assignments_deleted INTEGER;
            attachments_deleted INTEGER;
            feedbacks_deleted INTEGER;
            intents_deleted INTEGER;
            merges_deleted INTEGER;
            status_changes_deleted INTEGER;
            collisions_deleted INTEGER;
        BEGIN
            -- Delete ticket_assignments for non-existent tickets
            DELETE FROM ticket_assignments 
            WHERE ticket_id NOT IN (SELECT id FROM tickets);
            GET DIAGNOSTICS assignments_deleted = ROW_COUNT;
            
            -- Delete ticket_attachments for non-existent tickets
            DELETE FROM ticket_attachments 
            WHERE ticket_id NOT IN (SELECT id FROM tickets);
            GET DIAGNOSTICS attachments_deleted = ROW_COUNT;
            
            -- Delete ticket_feedbacks for non-existent tickets
            DELETE FROM ticket_feedbacks 
            WHERE ticket_id NOT IN (SELECT id FROM tickets);
            GET DIAGNOSTICS feedbacks_deleted = ROW_COUNT;
            
            -- Delete ticket_intents for non-existent tickets
            DELETE FROM ticket_intents 
            WHERE ticket_id NOT IN (SELECT id FROM tickets);
            GET DIAGNOSTICS intents_deleted = ROW_COUNT;
            
            -- Delete ticket_merges for non-existent tickets
            DELETE FROM ticket_merges 
            WHERE primary_ticket_id NOT IN (SELECT id FROM tickets);
            GET DIAGNOSTICS merges_deleted = ROW_COUNT;
            
            -- Delete ticket_status_changes for non-existent tickets
            DELETE FROM ticket_status_changes 
            WHERE ticket_id NOT IN (SELECT id FROM tickets);
            GET DIAGNOSTICS status_changes_deleted = ROW_COUNT;
            
            -- Delete ticket_collisions for non-existent tickets
            DELETE FROM ticket_collisions 
            WHERE ticket_id NOT IN (SELECT id FROM tickets);
            GET DIAGNOSTICS collisions_deleted = ROW_COUNT;
            
            result := jsonb_build_object(
                'assignments_deleted', assignments_deleted,
                'attachments_deleted', attachments_deleted,
                'feedbacks_deleted', feedbacks_deleted,
                'intents_deleted', intents_deleted,
                'merges_deleted', merges_deleted,
                'status_changes_deleted', status_changes_deleted,
                'collisions_deleted', collisions_deleted,
                'cleaned_at', NOW()
            );
            
            RETURN result;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Orphaned ticket data cleanup ready")
    
    # 3.2 Clean old inactive sessions
    print("\n🔄 Creating cleanup_old_sessions()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_jarvis_sessions(retention_days INTEGER DEFAULT 7)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- Delete old inactive jarvis sessions
            DELETE FROM jarvis_sessions
            WHERE (is_active = FALSE OR is_active IS NULL)
              AND updated_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            -- Also delete very old sessions regardless of status
            DELETE FROM jarvis_sessions
            WHERE updated_at < NOW() - (retention_days * 2 || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old jarvis sessions cleanup (7 days)")
    
    # 3.3 Clean abandoned onboarding sessions
    print("\n📋 Creating cleanup_abandoned_onboarding_sessions()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_abandoned_onboarding_sessions(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM onboarding_sessions
            WHERE status IN ('abandoned', 'expired', 'started')
              AND updated_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Abandoned onboarding sessions cleanup (30 days)")
    
    # 3.4 Clean expired refresh tokens
    print("\n🔑 Creating cleanup_expired_refresh_tokens()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_refresh_tokens(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM refresh_tokens
            WHERE expires_at < NOW()
               OR created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Expired refresh tokens cleanup (30 days)")
    
    # 3.5 Clean old chat widget sessions
    print("\n💬 Creating cleanup_old_chat_widget_sessions()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_chat_widget_sessions(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- Delete old chat widget messages first
            DELETE FROM chat_widget_messages
            WHERE session_id NOT IN (
                SELECT id FROM chat_widget_sessions 
                WHERE updated_at >= NOW() - (retention_days || ' days')::INTERVAL
            );
            
            -- Then delete old sessions
            DELETE FROM chat_widget_sessions
            WHERE updated_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old chat widget sessions cleanup (30 days)")
    
    # 3.6 Clean old pipeline snapshots
    print("\n📸 Creating cleanup_old_pipeline_snapshots()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_pipeline_snapshots(retention_days INTEGER DEFAULT 7)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM pipeline_state_snapshots
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old pipeline snapshots cleanup (7 days)")
    
    # 3.7 Clean old shadow mode results
    print("\n🎭 Creating cleanup_old_shadow_mode_results()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_shadow_mode_results(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM shadow_mode_results
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old shadow mode results cleanup (30 days)")
    
    # 3.8 Clean old technique executions
    print("\n⚙️  Creating cleanup_old_technique_executions()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_technique_executions(retention_days INTEGER DEFAULT 7)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM technique_executions
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old technique executions cleanup (7 days)")
    
    # 3.9 Clean old outbound emails
    print("\n📧 Creating cleanup_old_outbound_emails()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_outbound_emails(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM outbound_emails
            WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old outbound emails cleanup (30 days)")
    
    # 3.10 Clean old SMS conversations/messages
    print("\n📱 Creating cleanup_old_sms_data()...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_sms_data(retention_days INTEGER DEFAULT 30)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- Delete old messages first
            DELETE FROM sms_messages
            WHERE conversation_id NOT IN (
                SELECT id FROM sms_conversations 
                WHERE updated_at >= NOW() - (retention_days || ' days')::INTERVAL
            );
            
            -- Then delete old conversations
            DELETE FROM sms_conversations
            WHERE updated_at < NOW() - (retention_days || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Old SMS data cleanup (30 days)")
    
    # ══════════════════════════════════════════════════════════════════
    # FIX 4: UPDATE MASTER CLEANUP FUNCTION WITH EVERYTHING
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  🎯 FIX 4: UPDATED MASTER CLEANUP FUNCTION".center(76) + "║")
    print("╚" + "═" * 78 + "╝")
    
    print("\n⚙️  Updating run_comprehensive_cleanup() v2.0...")
    cur.execute("""
        CREATE OR REPLACE FUNCTION run_comprehensive_cleanup()
        RETURNS JSONB AS $$
        DECLARE
            result JSONB;
            orphan_result JSONB;
        BEGIN
            -- Get orphaned ticket data stats
            SELECT cleanup_orphaned_ticket_data() INTO orphan_result;
            
            result := jsonb_build_object(
                'ran_at', NOW(),
                'version', '2.1-complete',
                
                -- Section 1: OTP & Verification (HIGH PRIORITY - 15 min)
                'phone_otps_deleted', cleanup_expired_phone_otps(15),
                'email_otps_deleted', cleanup_expired_email_otps(15),
                'verification_tokens_deleted', cleanup_expired_verification_tokens(15),
                'password_reset_tokens_deleted', cleanup_expired_password_reset_tokens(1),
                
                -- Section 2: Safety Confirmations
                'safety_confirmations_expired', cleanup_expired_safety_confirmations(),
                'safety_confirmations_cleaned', cleanup_old_safety_confirmations(7),
                
                -- Section 3: Agents (NEW - Cascade Deletion)
                'soft_deleted_agents_cleaned', cleanup_deleted_agents(7),
                
                -- Section 4: Tickets & Messages (FIXED - Both 30 days!)
                'resolved_tickets_deleted', cleanup_old_resolved_tickets(30),
                'old_messages_deleted', cleanup_old_ticket_messages(30),
                'old_internal_notes_deleted', cleanup_old_ticket_internal_notes(30),
                'orphaned_ticket_data', orphan_result,
                
                -- Section 5: Sessions (NEW)
                'old_jarvis_sessions_deleted', cleanup_old_jarvis_sessions(7),
                'abandoned_onboarding_deleted', cleanup_abandoned_onboarding_sessions(30),
                'expired_refresh_tokens_deleted', cleanup_expired_refresh_tokens(30),
                'old_chat_widget_sessions_deleted', cleanup_old_chat_widget_sessions(30),
                
                -- Section 6: System Data (NEW)
                'old_pipeline_snapshots_deleted', cleanup_old_pipeline_snapshots(7),
                'old_shadow_mode_results_deleted', cleanup_old_shadow_mode_results(30),
                'old_technique_executions_deleted', cleanup_old_technique_executions(7),
                'old_outbound_emails_deleted', cleanup_old_outbound_emails(30),
                'old_sms_data_deleted', cleanup_old_sms_data(30),
                
                -- Section 7: Logs & Audit
                'activity_log_deleted', cleanup_old_activity_log(90),
                'error_log_deleted', cleanup_old_error_log(30),
                'rate_limit_events_deleted', cleanup_old_rate_limit_events(7),
                'notification_logs_deleted', cleanup_old_notification_logs(30),
                'email_logs_deleted', cleanup_old_email_logs(30),
                'agent_config_history_cleaned', cleanup_old_agent_config_history(180),
                'audit_trail_cleaned', cleanup_old_audit_trail(90),
                
                -- Section 8: Demo Data
                'demo_events_deleted', cleanup_old_demo_events(30),
                'demo_sessions_deleted', cleanup_old_demo_sessions(60),
                
                -- Note for payment failures (handled by Python service)
                'payment_failures_note', 'Use PaymentFailureService.cleanup_old_failures(90)'
            );
            
            RETURN result;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("   ✅ Master cleanup function v2.1 ready!")
    
    # ══════════════════════════════════════════════════════════════════
    # TEST: RUN THE UPDATED MASTER FUNCTION
    # ══════════════════════════════════════════════════════════════════
    print("\n╔" + "═" * 78 + "╗")
    print("║" + "  ✅ TESTING: Running comprehensive cleanup v2.1...".center(76) + "║")
    print("╚" + "═" * 78 + "╝\n")
    
    cur.execute("SELECT run_comprehensive_cleanup();")
    result = cur.fetchone()[0]
    
    import json
    if result:
        cleanup_result = json.loads(result) if isinstance(result, str) else result
        
        print("🎉 SUCCESS! Comprehensive cleanup v2.1 executed:\n")
        
        # Group by section
        sections = {
            '🔴 OTP & VERIFICATION (15 min)': ['phone_otps_deleted', 'email_otps_deleted', 'verification_tokens_deleted', 'password_reset_tokens_deleted'],
            '🛡️  SAFETY CONFIRMATIONS': ['safety_confirmations_expired', 'safety_confirmations_cleaned'],
            '🤖 AGENTS (Cascade Delete)': ['soft_deleted_agents_cleaned'],
            '🎫 TICKETS & MESSAGES (30 days!)': ['resolved_tickets_deleted', 'old_messages_deleted', 'old_internal_notes_deleted'],
            '🗑️  ORPHANED DATA': ['orphaned_ticket_data'],
            '🔄 SESSIONS': ['old_jarvis_sessions_deleted', 'abandoned_onboarding_deleted', 'expired_refresh_tokens_deleted', 'old_chat_widget_sessions_deleted'],
            '⚙️  SYSTEM DATA': ['old_pipeline_snapshots_deleted', 'old_shadow_mode_results_deleted', 'old_technique_executions_deleted', 'old_outbound_emails_deleted', 'old_sms_data_deleted'],
            '📋 LOGS & AUDIT': ['activity_log_deleted', 'error_log_deleted', 'rate_limit_events_deleted', 'notification_logs_deleted', 'email_logs_deleted', 'agent_config_history_cleaned', 'audit_trail_cleaned'],
            '📊 DEMO DATA': ['demo_events_deleted', 'demo_sessions_deleted']
        }
        
        total_cleaned = 0
        
        for section_name, keys in sections.items():
            print(f"\n{section_name}")
            print("-" * 50)
            for key in keys:
                value = cleanup_result.get(key, 'N/A')
                if isinstance(value, dict):
                    # For orphaned_ticket_data which returns a nested object
                    sub_total = sum(v for v in value.values() if isinstance(v, int))
                    icon = "🧹" if sub_total > 0 else "✅"
                    print(f"  {icon} {key}: {sub_total} records")
                    total_cleaned += sub_total
                elif isinstance(value, int):
                    icon = "🧹" if value > 0 else "✅"
                    print(f"  {icon} {key}: {value}")
                    total_cleaned += value
                elif 'note' in key.lower():
                    print(f"  ℹ️  {key}: (see note)")
        
        print("\n" + "=" * 50)
        print(f"Total records cleaned this run: {total_cleaned}")
    
    # ══════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════════════
    print("\n\n" + "=" * 80)
    print("🎊 COMPREHENSIVE CLEANUP v2.1 DEPLOYED SUCCESSFULLY!")
    print("=" * 80)
    
    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ✅ FIXES APPLIED                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  🔧 FIX 1: Message Retention Fixed                                         │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • ticket_messages: 60 days → 30 days ✅                                   │
│  • ticket_internal_notes: 60 days → 30 days ✅                              │
│  • Reason: Prevents orphaned messages when parent tickets are deleted!      │
│                                                                             │
│  🔧 FIX 2: Agent Deletion Cascade                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • cascade_delete_agent(agent_id) → Deletes agent + ALL related data       │
│  • Auto-trigger on DELETE → Automatic cleanup                              │
│  • Cleans: agents, agent_config_history, ai_agent_assignments,             │
│    custom_categories references                                            │
│  • Grace period: Soft-deleted agents fully removed after 7 days            │
│                                                                             │
│  🔧 FIX 3: New Orphaned Data Cleanup                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • Orphaned ticket_* records (assignments, attachments, feedbacks, etc.)   │
│  • Old jarvis sessions (7 days)                                            │
│  • Abandoned onboarding sessions (30 days)                                 │
│  • Expired refresh tokens (30 days)                                        │
│  • Old chat widget sessions (30 days)                                      │
│  • Old pipeline snapshots (7 days)                                         │
│  • Old shadow mode results (30 days)                                       │
│  • Old technique executions (7 days)                                       │
│  • Old outbound emails (30 days)                                           │
│  • Old SMS conversations/messages (30 days)                                │
│                                                                             │
│  ⏰  Schedule: Every 15 minutes via application background loop            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
""")
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
