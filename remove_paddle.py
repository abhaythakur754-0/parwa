#!/usr/bin/env python3
"""
Remove Paddle from master cleanup - v3.1
"""
import psycopg2

DB_CONFIG = {
    'host': 'aws-1-ap-northeast-1.pooler.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.fmpibdauppnzfisodkhp',
    'password': 'Durgamaa@754'
}

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True
cur = conn.cursor()

# Update master cleanup to remove Paddle, keep only Parwa payments
sql = """
CREATE OR REPLACE FUNCTION run_comprehensive_cleanup()
RETURNS JSONB AS $$
DECLARE
    result JSONB;
    payment JSONB;
    ai_ml JSONB;
    logs JSONB;
    system_temp JSONB;
    other JSONB;
    original JSONB;
BEGIN
    -- Section A: PARWA PAYMENTS (NO Paddle!)
    payment := jsonb_build_object(
        'parwa_payments', cleanup_old_parwa_payments(90),
        'parwa_orders', cleanup_old_parwa_orders(180),
        'parwa_invoices', cleanup_old_parwa_invoices(365),
        'parwa_refunds', cleanup_old_parwa_refunds(365),
        'overage_charges', cleanup_old_overage_charges(90),
        'proration_audits', cleanup_old_proration_audits(90),
        'client_refunds', cleanup_old_client_refunds(365),
        'transactions', cleanup_old_transactions(180)
    );
    
    -- Section B: AI/ML PERFORMANCE
    ai_ml := jsonb_build_object(
        'ai_performance_metrics', cleanup_old_ai_performance_metrics(30),
        'ai_response_feedback', cleanup_old_ai_response_feedback(30),
        'model_usage_logs', cleanup_old_model_usage_logs(90),
        'agent_performance', cleanup_old_agent_performance(90),
        'agent_mistakes', cleanup_old_agent_mistakes(90),
        'qa_scores', cleanup_old_qa_scores(90),
        'training_runs', cleanup_old_training_runs(30),
        'technique_caches', cleanup_old_technique_caches(7),
        'variant_instances', cleanup_old_variant_instances(30),
        'variant_workload', cleanup_old_variant_workload_distribution(30),
        'metric_aggregates', cleanup_old_metric_aggregates(30)
    );
    
    -- Section C: ADDITIONAL LOGS
    logs := jsonb_build_object(
        'guardrails_audit_log', cleanup_old_guardrails_audit_log(30),
        'guardrail_blocks', cleanup_old_guardrail_blocks(30),
        'prompt_injection', cleanup_old_prompt_injection_attempts(30),
        'ooo_detection_log', cleanup_old_ooo_detection_log(30),
        'api_key_audit_log', cleanup_old_api_key_audit_log(90),
        'identity_match_logs', cleanup_old_identity_match_logs(30),
        'classification_log', cleanup_old_classification_log(30),
        'email_delivery_events', cleanup_old_email_delivery_events(30),
        'bulk_action_logs', cleanup_old_bulk_action_logs(30),
        'customer_merge_audits', cleanup_old_customer_merge_audits(90),
        'jarvis_activity_events', cleanup_old_jarvis_activity_events(30),
        'notification_pref_audit', cleanup_old_notification_preference_audit(90),
        'webhook_events', cleanup_old_webhook_events(30),
        'undo_log', cleanup_old_undo_log(7),
        'event_buffer', cleanup_old_event_buffer(24)
    );
    
    -- Section D: SYSTEM TEMP
    system_temp := jsonb_build_object(
        'idempotency_keys', cleanup_old_idempotency_keys(24),
        'checkpoints', cleanup_old_checkpoints(7),
        'sla_timers', cleanup_expired_sla_timers(),
        'guardrails_blocked_queue', cleanup_old_guardrails_blocked_queue(1),
        'approval_queues', cleanup_old_approval_queues(7),
        'approval_batches', cleanup_old_approval_batches(30),
        'training_checkpoints', cleanup_old_training_checkpoints(7),
        'jarvis_awareness_snapshots', cleanup_old_jarvis_awareness_snapshots(7),
        'roi_snapshots', cleanup_old_roi_snapshots(90)
    );
    
    -- Section E: OTHER
    other := jsonb_build_object(
        'notifications', cleanup_old_notifications(30),
        'jarvis_proactive_alerts', cleanup_old_jarvis_proactive_alerts(30),
        'jarvis_action_tickets', cleanup_old_jarvis_action_tickets(30),
        'cancellation_requests', cleanup_old_cancellation_requests(90),
        'usage_records', cleanup_old_usage_records(180),
        'demo_sessions', cleanup_old_demo_sessions(60),
        'voice_calls', cleanup_old_voice_calls(30),
        'voice_conversations', cleanup_old_voice_conversations(30),
        'outgoing_webhooks', cleanup_old_outgoing_webhooks(30),
        'webhook_sequences', cleanup_old_webhook_sequences(30),
        'inbound_emails', cleanup_old_inbound_emails(30),
        'email_threads', cleanup_old_email_threads(90),
        'drift_reports', cleanup_old_drift_reports(90),
        'rate_limit_counters', cleanup_old_rate_limit_counters()
    );
    
    -- Original sections (from v2.1)
    original := jsonb_build_object(
        'phone_otps', cleanup_expired_phone_otps(15),
        'email_otps', cleanup_expired_email_otps(15),
        'verification_tokens', cleanup_expired_verification_tokens(15),
        'password_reset_tokens', cleanup_expired_password_reset_tokens(1),
        'safety_confirmations_expired', cleanup_expired_safety_confirmations(),
        'safety_confirmations_cleaned', cleanup_old_safety_confirmations(7),
        'soft_deleted_agents', cleanup_deleted_agents(7),
        'resolved_tickets', cleanup_old_resolved_tickets(30),
        'ticket_messages', cleanup_old_ticket_messages(30),
        'ticket_internal_notes', cleanup_old_ticket_internal_notes(30),
        'jarvis_sessions', cleanup_old_jarvis_sessions(7),
        'onboarding_sessions', cleanup_abandoned_onboarding_sessions(30),
        'refresh_tokens', cleanup_expired_refresh_tokens(30),
        'chat_widget_sessions', cleanup_old_chat_widget_sessions(30),
        'pipeline_snapshots', cleanup_old_pipeline_snapshots(7),
        'shadow_mode_results', cleanup_old_shadow_mode_results(30),
        'technique_executions', cleanup_old_technique_executions(7),
        'outbound_emails_v2', cleanup_old_outbound_emails(30),
        'sms_data', cleanup_old_sms_data(30),
        'activity_log', cleanup_old_activity_log(90),
        'error_log', cleanup_old_error_log(30),
        'rate_limit_events', cleanup_old_rate_limit_events(7),
        'notification_logs', cleanup_old_notification_logs(30),
        'email_logs', cleanup_old_email_logs(30),
        'agent_config_history', cleanup_old_agent_config_history(180),
        'audit_trail', cleanup_old_audit_trail(90),
        'demo_events', cleanup_old_demo_events(30),
        'demo_sessions_v2', cleanup_old_demo_sessions(60)
    );
    
    result := jsonb_build_object(
        'ran_at', NOW(),
        'version', '3.1-no-paddle',
        'parwa_payments', payment,
        'ai_ml_performance', ai_ml,
        'additional_logs', logs,
        'system_temp', system_temp,
        'other_data', other,
        'original_cleanup', original,
        'payment_failures_note', 'Use PaymentFailureService.cleanup_old_failures(90)'
    );
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;
"""

cur.execute(sql)

print("✅ Master cleanup updated to v3.1 - PADDLE REMOVED!")

# Test it
cur.execute("SELECT run_comprehensive_cleanup();")
result = cur.fetchone()[0]

import json
r = json.loads(result) if isinstance(result, str) else result

print("\n🎉 SUCCESS! v3.1 runs clean - NO PADDLE!")
print("\n💰 YOUR Parwa Payment Cleanup:")
for k,v in r.get('parwa_payments',{}).items():
    print(f"  • {k}: {v} records")

cur.close()
conn.close()
