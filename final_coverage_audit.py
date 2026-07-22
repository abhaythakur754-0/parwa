#!/usr/bin/env python3
"""
FINAL COMPREHENSIVE AUDIT - Are we missing any data cleanup?
Check ALL 139 tables against our cleanup functions
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

print("=" * 90)
print("🔍 FINAL AUDIT: Checking ALL Tables Against Cleanup Coverage")
print(f"   Time: {datetime.now().isoformat()}")
print("=" * 90)

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Get ALL tables with row counts
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    
    all_tables = [row[0] for row in cur.fetchall()]
    
    # Define what we ARE cleaning (from run_comprehensive_cleanup v2.1)
    covered_tables = {
        # OTP & Verification
        'phone_otps': {'retention': '15 min', 'function': 'cleanup_expired_phone_otps'},
        'business_email_otps': {'retention': '15 min', 'function': 'cleanup_expired_email_otps'},
        'verification_tokens': {'retention': '15 min', 'function': 'cleanup_expired_verification_tokens'},
        'password_reset_tokens': {'retention': '1 hour', 'function': 'cleanup_expired_password_reset_tokens'},
        
        # Safety
        'jarvis_safety_confirmations': {'retention': '7 days', 'function': 'cleanup_old_safety_confirmations'},
        
        # Agents
        'agents': {'retention': 'cascade on delete', 'function': 'cascade_delete_agent / trigger'},
        'agent_config_history': {'retention': '180 days', 'function': 'cleanup_old_agent_config_history'},
        'ai_agent_assignments': {'retention': 'cascade on delete', 'function': 'cascade delete'},
        
        # Tickets & Messages
        'tickets': {'retention': '30 days (resolved)', 'function': 'cleanup_old_resolved_tickets'},
        'ticket_messages': {'retention': '30 days ⬅️ FIXED', 'function': 'cleanup_old_ticket_messages'},
        'ticket_internal_notes': {'retention': '30 days ⬅️ FIXED', 'function': 'cleanup_old_ticket_internal_notes'},
        
        # Ticket-related (orphaned cleanup)
        'ticket_assignments': {'retention': 'orphaned cleanup', 'function': 'cleanup_orphaned_ticket_data'},
        'ticket_attachments': {'retention': 'orphaned cleanup', 'function': 'cleanup_orphaned_ticket_data'},
        'ticket_feedbacks': {'retention': 'orphaned cleanup', 'function': 'cleanup_orphaned_ticket_data'},
        'ticket_intents': {'retention': 'orphaned cleanup', 'function': 'cleanup_orphaned_ticket_data'},
        'ticket_merges': {'retention': 'orphaned cleanup', 'function': 'cleanup_orphaned_ticket_data'},
        'ticket_status_changes': {'retention': 'orphaned cleanup', 'function': 'cleanup_orphaned_ticket_data'},
        'ticket_collisions': {'retention': 'orphaned cleanup', 'function': 'cleanup_orphaned_ticket_data'},
        'ticket_triggers': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Sessions
        'jarvis_sessions': {'retention': '7 days', 'function': 'cleanup_old_jarvis_sessions'},
        'onboarding_sessions': {'retention': '30 days', 'function': 'cleanup_abandoned_onboarding_sessions'},
        'refresh_tokens': {'retention': '30 days', 'function': 'cleanup_expired_refresh_tokens'},
        'chat_widget_sessions': {'retention': '30 days', 'function': 'cleanup_old_chat_widget_sessions'},
        'chat_widget_messages': {'retention': '30 days', 'function': 'cleanup_old_chat_widget_sessions'},
        'sms_conversations': {'retention': '30 days', 'function': 'cleanup_old_sms_data'},
        'sms_messages': {'retention': '30 days', 'function': 'cleanup_old_sms_data'},
        
        # System Data
        'pipeline_state_snapshots': {'retention': '7 days', 'function': 'cleanup_old_pipeline_snapshots'},
        'shadow_mode_results': {'retention': '30 days', 'function': 'cleanup_old_shadow_mode_results'},
        'technique_executions': {'retention': '7 days', 'function': 'cleanup_old_technique_executions'},
        'outbound_emails': {'retention': '30 days', 'function': 'cleanup_old_outbound_emails'},
        
        # Logs & Audit
        'activity_log': {'retention': '90 days', 'function': 'cleanup_old_activity_log'},
        'error_log': {'retention': '30 days', 'function': 'cleanup_old_error_log'},
        'rate_limit_events': {'retention': '7 days', 'function': 'cleanup_old_rate_limit_events'},
        'notification_logs': {'retention': '30 days', 'function': 'cleanup_old_notification_logs'},
        'email_logs': {'retention': '30 days', 'function': 'cleanup_old_email_logs'},
        'email_delivery_events': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'audit_trail': {'retention': '90 days', 'function': 'cleanup_old_audit_trail'},
        
        # Demo Data
        'demo_usage_events': {'retention': '30 days', 'function': 'cleanup_old_demo_events'},
        'demo_usage_sessions': {'retention': '60 days', 'function': 'cleanup_old_demo_sessions'},
        'demo_sessions': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Payment Data
        'payment_failures': {'retention': '90 days (Python)', 'function': 'PaymentFailureService'},
        'payment_methods': {'retention': 'NEVER (user data)', 'function': 'N/A'},
        'transactions': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'overage_charges': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'proration_audits': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'paddle_webhook_events': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'paddle_reconciliation_reports': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'parwa_payments': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'parwa_invoices': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'parwa_orders': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'parwa_refunds': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'parwa_customers': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'parwa_escalation_vault': {'retention': 'NEVER (active data)', 'function': 'N/A'},
        
        # Variant/AI Performance Data
        'ai_performance_variant_metrics': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'ai_response_feedback': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'ai_token_budgets': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'ai_wiki_entries': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'variant_instances': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'variant_limits': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'variant_workload_distribution': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'variant_ai_capabilities': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'agent_performance': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'agent_mistakes': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'qa_scores': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Training Data
        'training_runs': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'training_datasets': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'training_checkpoints': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'technique_caches': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'technique_configurations': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'technique_versions': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Security/Auth
        'mfa_secrets': {'retention': 'NEVER (security)', 'function': 'N/A'},
        'backup_codes': {'retention': 'NEVER (security)', 'function': 'N/A'},
        'oauth_accounts': {'retention': 'NEVER (auth)', 'function': 'N/A'},
        'api_keys': {'retention': 'NEVER (user config)', 'function': 'N/A'},
        'api_key_audit_log': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'api_providers': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'consent_records': {'retention': 'NEVER (legal)', 'function': 'N/A'},
        'idempotency_keys': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Notification System
        'notifications': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'notification_preferences': {'retention': 'NEVER (user pref)', 'function': 'N/A'},
        'notification_preference_audit': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'notification_templates': {'retention': 'NEVER (templates)', 'function': 'N/A'},
        
        # Email System
        'inbound_emails': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'email_threads': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'email_bounces': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'email_deliverability_alerts': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Voice System
        'voice_calls': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'voice_channel_configs': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'voice_conversations': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Webhook System
        'webhook_events': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'webhook_integrations': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'webhook_sequences': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'outgoing_webhooks': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # Other System Tables
        'ooo_detection_rules': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'ooo_sender_profiles': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'ooo_detection_log': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'sla_policies': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'sla_timers': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'channels': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'channel_configs': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'canned_responses': {'retention': 'NEVER (templates)', 'function': 'N/A'},
        'custom_fields': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'data_retention_policies': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'feature_flags': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'guardrail_blocks': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'guardrail_rules': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'guardrails_blocked_queue': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'guardrails_audit_log': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'prompt_injection_attempts': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'prompt_templates': {'retention': 'NEVER (templates)', 'function': 'N/A'},
        'response_templates': {'retention': 'NEVER (templates)', 'function': 'N/A'},
        'service_configs': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'shadow_mode_configs': {'retention': 'NEVER (config)', 'function': 'N/A'},
        
        # Knowledge Base
        'knowledge_base': {'retention': 'NEVER (core data)', 'function': 'N/A'},
        'knowledge_documents': {'retention': 'NEVER (core data)', 'function': 'N/A'},
        'document_chunks': {'retention': 'NEVER (core data)', 'function': 'N/A'},
        'jarvis_knowledge_used': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'jarvis_awareness_snapshots': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'jarvis_commands': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'jarvis_proactive_alerts': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'jarvis_action_tickets': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'jarvis_messages': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'jarvis_activity_events': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        
        # User/Core Data (NEVER DELETE)
        'users': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'user_details': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'companies': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'company_settings': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'customers': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'customer_channels': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'customer_email_status': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'integrations': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'rest_connectors': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'subscriptions': {'retention': 'NEVER (core)', 'function': 'N/A'},
        'invoices': {'retention': 'NEVER (financial)', 'function': 'N/A'},
        'cancellation_requests': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'client_refunds': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'newsletter_subscribers': {'retention': 'NEVER (marketing)', 'function': 'N/A'},
        'usage_records': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'user_notification_preferences': {'retention': 'NEVER (pref)', 'function': 'N/A'},
        'identity_match_logs': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'customer_merge_audits': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'classification_log': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'classification_corrections': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'bulk_action_failures': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'bulk_action_logs': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'model_usage_logs': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'confidence_scores': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'confidence_thresholds': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'drift_reports': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'executed_actions': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'first_victories': {'retention': '❓ NOT COVERED', 'function': 'N/A'},
        'gsd_sessions': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'human_corrections': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'erasure_requests': {'retention': 'NEVER (legal)', 'function': 'N/A'},
        'emergency_states': {'retention': 'NEVER (system)', 'function': 'N/A'},
        'db_connections': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'undo_log': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'event_buffer': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'roi_snapshots': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'approval_batches': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'approval_queues': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'auto_approve_rules': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'assignment_rules': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'checkpoint_blobs': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'checkpoint_migrations': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'checkpoint_writes': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'checkpoints': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'mcp_connections': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'metric_aggregates': {'retention': '❓ NOT COVERED', 'function': 'NONE'},
        'sms_channel_configs': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'chat_widget_configs': {'retention': 'NEVER (config)', 'function': 'N/A'},
        'tickets_archive': {'retention': 'archive only', 'function': 'archive_old_tickets'},
        'alembic_version': {'retention': 'system', 'function': 'N/A'},
        'custom_categories': {'retention': 'cleared on agent del', 'function': 'cascade'},
    }
    
    print("\n" + "╔" + "═" * 88 + "╗")
    print("║" + "  📊 COVERAGE ANALYSIS".center(86) + "║")
    print("╚" + "═" * 88 + "╝\n")
    
    covered_count = 0
    not_covered_count = 0
    never_delete_count = 0
    
    covered_tables_list = []
    not_covered_tables_list = []
    never_delete_tables_list = []
    
    for table in sorted(all_tables):
        info = covered_tables.get(table, {'retention': '❌ MISSING!', 'function': 'NOT FOUND'})
        
        retention = info.get('retention', '❌ MISSING!')
        
        if 'NOT COVERED' in retention or 'MISSING' in retention:
            not_covered_count += 1
            not_covered_tables_list.append((table, info.get('function', 'NONE')))
            icon = "❌"
        elif retention == 'NEVER' or 'NEVER (' in retention:
            never_delete_count += 1
            never_delete_tables_list.append(table)
            icon = "🔒"
        else:
            covered_count += 1
            covered_tables_list.append(table)
            icon = "✅"
        
        # Only print summary, not every table (too long)
    
    print(f"{'Category':<25} {'Count':>8} {'Percentage':>12}")
    print("-" * 50)
    total = len(all_tables)
    print(f"{'✅ COVERED by cleanup':<25} {covered_count:>8} {covered_count/total*100:>11.1f}%")
    print(f"{'❌ NOT COVERED':<25} {not_covered_count:>8} {not_covered_count/total*100:>11.1f}%")
    print(f"{'🔒 NEVER DELETE (Core)':<25} {never_delete_count:>8} {never_delete_count/total*100:>11.1f}%")
    print("-" * 50)
    print(f"{'TOTAL TABLES':<25} {total:>8} {'100%':>12}")
    
    # ══════════════════════════════════════════════════════════════════
    # SHOW NOT COVERED TABLES - THESE NEED ATTENTION!
    # ══════════════════════════════════════════════════════════════════
    if not_covered_tables_list:
        print("\n\n" + "╔" + "═" * 88 + "╗")
        print("║" + "  ❌ TABLES NOT COVERED BY CLEANUP - NEEDS ATTENTION!".center(86) + "║")
        print("╚" + "═" * 88 + "╝\n")
        
        # Group by category
        payment_variant_tables = []
        log_audit_tables = []
        system_temp_tables = []
        ai_ml_tables = []
        other_tables = []
        
        for table, func in not_covered_tables_list:
            if any(x in table.lower() for x in ['payment', 'parwa_', 'transaction', 'overage', 'proration', 'paddle', 'invoice', 'order', 'refund']):
                payment_variant_tables.append((table, func))
            elif any(x in table.lower() for x in ['log', 'audit', 'event', 'attempt', 'feedback']):
                log_audit_tables.append((table, func))
            elif any(x in table.lower() for x in ['temp', 'buffer', 'undo', 'idempotency', 'checkpoint', 'snapshot', 'queue', 'timer']):
                system_temp_tables.append((table, func))
            elif any(x in table.lower() for x in ['ai_', 'performance', 'training', 'technique', 'model', 'variant', 'metric', 'qa_', 'mistake']):
                ai_ml_tables.append((table, func))
            else:
                other_tables.append((table, func))
        
        if payment_variant_tables:
            print("\n💰 PAYMENT / VARIANT DATA (IMPORTANT!):")
            print("-" * 70)
            for table, func in payment_variant_tables:
                print(f"   ❌ {table:<40} → Need cleanup function!")
        
        if log_audit_tables:
            print("\n📋 LOGS & AUDIT DATA:")
            print("-" * 70)
            for table, func in log_audit_tables:
                print(f"   ❌ {table:<40} → Should add cleanup")
        
        if system_temp_tables:
            print("\n⚙️  SYSTEM TEMP DATA:")
            print("-" * 70)
            for table, func in system_temp_tables:
                print(f"   ❌ {table:<40} → Can be cleaned")
        
        if ai_ml_tables:
            print("\n🤖 AI/ML PERFORMANCE DATA:")
            print("-" * 70)
            for table, func in ai_ml_tables:
                print(f"   ❌ {table:<40} → Can be cleaned")
        
        if other_tables:
            print("\n📦 OTHER UNCOVERED:")
            print("-" * 70)
            for table, func in other_tables:
                print(f"   ❌ {table:<40} → Review needed")
    
    # ══════════════════════════════════════════════════════════════════
    # RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════
    print("\n\n" + "╔" + "═" * 88 + "╗")
    print("║" + "  🎯 RECOMMENDATIONS FOR COMPLETE COVERAGE".center(86) + "║")
    print("╚" + "═" * 88 + "╝")
    
    recommendations = """
┌─────────────────────────────────────────────────────────────────────────────┐
│  💰 PAYMENT/VARIANT DATA (User mentioned this!)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  • paddle_webhook_events     → Clean after 30 days                        │
│  • parwa_payments            → Keep 90 days (financial records)           │
│  • parwa_invoices            → Keep 365 days (accounting)                │
│  • parwa_orders              → Keep 180 days                             │
│  • parwa_refunds             → Keep 365 days (audit trail)               │
│  • transactions              → Keep 180 days                             │
│  • overage_charges           → Keep 90 days                              │
│  • proration_audits          → Keep 90 days                              │
│                                                                             │
│  🤖 AI/ML PERFORMANCE DATA                                                 │
│  ├────────────────────────────────────────────────────────────────────────  │
│  • ai_performance_variant_metrics → Keep 30 days (for analysis)          │
│  • ai_response_feedback         → Keep 30 days                           │
│  • model_usage_logs             → Keep 90 days (cost tracking!)          │
│  • agent_performance            → Keep 90 days                           │
│  • agent_mistakes               → Keep 90 days                           │
│  • qa_scores                    → Keep 90 days                           │
│  • training_runs                → Keep 30 days                           │
│  • technique_caches             → Clean after 7 days                     │
│                                                                             │
│  📋 ADDITIONAL LOGS                                                        │
│  ├────────────────────────────────────────────────────────────────────────  │
│  • guardrails_audit_log        → Keep 30 days                            │
│  • guardrail_blocks            → Keep 30 days                            │
│  • prompt_injection_attempts    → Keep 30 days (security important!)      │
│  • ooo_detection_log           → Keep 30 days                            │
│  • api_key_audit_log           → Keep 90 days (security audit)          │
│  • identity_match_logs         → Keep 30 days                            │
│  • classification_log          → Keep 30 days                            │
│                                                                             │
│  ⚙️  SYSTEM TEMP DATA                                                       │
│  ├────────────────────────────────────────────────────────────────────────  │
│  • idempotency_keys             → Clean after 24 hours                    │
│  • undo_log                     → Clean after 7 days                      │
│  • event_buffer                 → Clean after 1 day                       │
│  • checkpoints / checkpoint_*   → Clean after 7 days                     │
│  • sla_timers                   → Clean expired ones (daily)              │
│  • guardrails_blocked_queue     → Clean after 1 day                       │
│                                                                             │
│  🔔 OTHER                                                                  │
│  ├────────────────────────────────────────────────────────────────────────  │
│  • notifications                → Clean read/dismissed after 30 days      │
│  • webhook_events               → Clean after 30 days                     │
│  • cancellation_requests       → Keep 90 days                            │
│  • roi_snapshots                → Keep 90 days                            │
│  • usage_records                → Keep 180 days (billing imp!)            │
│  • jarvis_proactive_alerts      → Clean after 30 days                    │
│  • jarvis_action_tickets        → Clean resolved after 30 days           │
└─────────────────────────────────────────────────────────────────────────────┘
"""
    print(recommendations)
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
