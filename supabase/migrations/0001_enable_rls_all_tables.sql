-- Migration: Enable Row Level Security (RLS) on all public tables
-- Fixes Supabase Database Linter warnings:
--   - rls_disabled_in_public  (156 warnings)
--   - sensitive_columns_exposed (29 warnings)
--
-- Strategy:
--   1. ENABLE RLS on every table in the public schema.
--   2. FORCE RLS (so even table owners are subject to it; superuser still bypasses).
--   3. Add a permissive policy for the service_role (backend connects via
--      service-role Postgres connection string, which bypasses RLS anyway,
--      but an explicit policy is good practice).
--   4. The anon and authenticated Postgres roles get NO policies, so direct
--      browser access via the Supabase REST API is fully blocked. All app
--      traffic must go through the FastAPI backend (JWT + TenantMiddleware).
--
-- Idempotent: safe to re-run (uses IF NOT EXISTS / DROP IF EXISTS).
-- Generated from live database schema on 2025-06-24.

BEGIN;

-- Table: public."activity_log"
ALTER TABLE public."activity_log" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."activity_log" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_activity_log" ON public."activity_log";
CREATE POLICY "service_role_all_activity_log"
    ON public."activity_log"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."agent_mistakes"
ALTER TABLE public."agent_mistakes" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."agent_mistakes" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_agent_mistakes" ON public."agent_mistakes";
CREATE POLICY "service_role_all_agent_mistakes"
    ON public."agent_mistakes"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."agent_performance"
ALTER TABLE public."agent_performance" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."agent_performance" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_agent_performance" ON public."agent_performance";
CREATE POLICY "service_role_all_agent_performance"
    ON public."agent_performance"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."agents"
ALTER TABLE public."agents" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."agents" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_agents" ON public."agents";
CREATE POLICY "service_role_all_agents"
    ON public."agents"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ai_agent_assignments"
ALTER TABLE public."ai_agent_assignments" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ai_agent_assignments" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ai_agent_assignments" ON public."ai_agent_assignments";
CREATE POLICY "service_role_all_ai_agent_assignments"
    ON public."ai_agent_assignments"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ai_performance_variant_metrics"
ALTER TABLE public."ai_performance_variant_metrics" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ai_performance_variant_metrics" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ai_performance_variant_metrics" ON public."ai_performance_variant_metrics";
CREATE POLICY "service_role_all_ai_performance_variant_metrics"
    ON public."ai_performance_variant_metrics"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ai_response_feedback"
ALTER TABLE public."ai_response_feedback" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ai_response_feedback" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ai_response_feedback" ON public."ai_response_feedback";
CREATE POLICY "service_role_all_ai_response_feedback"
    ON public."ai_response_feedback"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ai_token_budgets"
ALTER TABLE public."ai_token_budgets" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ai_token_budgets" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ai_token_budgets" ON public."ai_token_budgets";
CREATE POLICY "service_role_all_ai_token_budgets"
    ON public."ai_token_budgets"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."api_key_audit_log"
ALTER TABLE public."api_key_audit_log" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."api_key_audit_log" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_api_key_audit_log" ON public."api_key_audit_log";
CREATE POLICY "service_role_all_api_key_audit_log"
    ON public."api_key_audit_log"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."api_keys"
ALTER TABLE public."api_keys" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."api_keys" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_api_keys" ON public."api_keys";
CREATE POLICY "service_role_all_api_keys"
    ON public."api_keys"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."api_providers"
ALTER TABLE public."api_providers" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."api_providers" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_api_providers" ON public."api_providers";
CREATE POLICY "service_role_all_api_providers"
    ON public."api_providers"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."approval_batches"
ALTER TABLE public."approval_batches" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."approval_batches" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_approval_batches" ON public."approval_batches";
CREATE POLICY "service_role_all_approval_batches"
    ON public."approval_batches"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."approval_queues"
ALTER TABLE public."approval_queues" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."approval_queues" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_approval_queues" ON public."approval_queues";
CREATE POLICY "service_role_all_approval_queues"
    ON public."approval_queues"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."assignment_rules"
ALTER TABLE public."assignment_rules" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."assignment_rules" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_assignment_rules" ON public."assignment_rules";
CREATE POLICY "service_role_all_assignment_rules"
    ON public."assignment_rules"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."audit_trail"
ALTER TABLE public."audit_trail" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."audit_trail" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_audit_trail" ON public."audit_trail";
CREATE POLICY "service_role_all_audit_trail"
    ON public."audit_trail"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."auto_approve_rules"
ALTER TABLE public."auto_approve_rules" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."auto_approve_rules" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_auto_approve_rules" ON public."auto_approve_rules";
CREATE POLICY "service_role_all_auto_approve_rules"
    ON public."auto_approve_rules"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."backup_codes"
ALTER TABLE public."backup_codes" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."backup_codes" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_backup_codes" ON public."backup_codes";
CREATE POLICY "service_role_all_backup_codes"
    ON public."backup_codes"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."bulk_action_failures"
ALTER TABLE public."bulk_action_failures" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."bulk_action_failures" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_bulk_action_failures" ON public."bulk_action_failures";
CREATE POLICY "service_role_all_bulk_action_failures"
    ON public."bulk_action_failures"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."bulk_action_logs"
ALTER TABLE public."bulk_action_logs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."bulk_action_logs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_bulk_action_logs" ON public."bulk_action_logs";
CREATE POLICY "service_role_all_bulk_action_logs"
    ON public."bulk_action_logs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."business_email_otps"
ALTER TABLE public."business_email_otps" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."business_email_otps" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_business_email_otps" ON public."business_email_otps";
CREATE POLICY "service_role_all_business_email_otps"
    ON public."business_email_otps"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."cancellation_requests"
ALTER TABLE public."cancellation_requests" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."cancellation_requests" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_cancellation_requests" ON public."cancellation_requests";
CREATE POLICY "service_role_all_cancellation_requests"
    ON public."cancellation_requests"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."canned_responses"
ALTER TABLE public."canned_responses" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."canned_responses" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_canned_responses" ON public."canned_responses";
CREATE POLICY "service_role_all_canned_responses"
    ON public."canned_responses"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."channel_configs"
ALTER TABLE public."channel_configs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."channel_configs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_channel_configs" ON public."channel_configs";
CREATE POLICY "service_role_all_channel_configs"
    ON public."channel_configs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."channels"
ALTER TABLE public."channels" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."channels" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_channels" ON public."channels";
CREATE POLICY "service_role_all_channels"
    ON public."channels"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."chat_widget_configs"
ALTER TABLE public."chat_widget_configs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."chat_widget_configs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_chat_widget_configs" ON public."chat_widget_configs";
CREATE POLICY "service_role_all_chat_widget_configs"
    ON public."chat_widget_configs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."chat_widget_messages"
ALTER TABLE public."chat_widget_messages" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."chat_widget_messages" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_chat_widget_messages" ON public."chat_widget_messages";
CREATE POLICY "service_role_all_chat_widget_messages"
    ON public."chat_widget_messages"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."chat_widget_sessions"
ALTER TABLE public."chat_widget_sessions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."chat_widget_sessions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_chat_widget_sessions" ON public."chat_widget_sessions";
CREATE POLICY "service_role_all_chat_widget_sessions"
    ON public."chat_widget_sessions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."classification_corrections"
ALTER TABLE public."classification_corrections" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."classification_corrections" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_classification_corrections" ON public."classification_corrections";
CREATE POLICY "service_role_all_classification_corrections"
    ON public."classification_corrections"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."classification_log"
ALTER TABLE public."classification_log" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."classification_log" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_classification_log" ON public."classification_log";
CREATE POLICY "service_role_all_classification_log"
    ON public."classification_log"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."client_refunds"
ALTER TABLE public."client_refunds" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."client_refunds" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_client_refunds" ON public."client_refunds";
CREATE POLICY "service_role_all_client_refunds"
    ON public."client_refunds"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."companies"
ALTER TABLE public."companies" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."companies" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_companies" ON public."companies";
CREATE POLICY "service_role_all_companies"
    ON public."companies"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."company_settings"
ALTER TABLE public."company_settings" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."company_settings" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_company_settings" ON public."company_settings";
CREATE POLICY "service_role_all_company_settings"
    ON public."company_settings"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."confidence_scores"
ALTER TABLE public."confidence_scores" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."confidence_scores" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_confidence_scores" ON public."confidence_scores";
CREATE POLICY "service_role_all_confidence_scores"
    ON public."confidence_scores"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."confidence_thresholds"
ALTER TABLE public."confidence_thresholds" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."confidence_thresholds" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_confidence_thresholds" ON public."confidence_thresholds";
CREATE POLICY "service_role_all_confidence_thresholds"
    ON public."confidence_thresholds"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."consent_records"
ALTER TABLE public."consent_records" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."consent_records" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_consent_records" ON public."consent_records";
CREATE POLICY "service_role_all_consent_records"
    ON public."consent_records"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."custom_fields"
ALTER TABLE public."custom_fields" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."custom_fields" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_custom_fields" ON public."custom_fields";
CREATE POLICY "service_role_all_custom_fields"
    ON public."custom_fields"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."customer_channels"
ALTER TABLE public."customer_channels" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."customer_channels" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_customer_channels" ON public."customer_channels";
CREATE POLICY "service_role_all_customer_channels"
    ON public."customer_channels"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."customer_email_status"
ALTER TABLE public."customer_email_status" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."customer_email_status" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_customer_email_status" ON public."customer_email_status";
CREATE POLICY "service_role_all_customer_email_status"
    ON public."customer_email_status"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."customer_merge_audits"
ALTER TABLE public."customer_merge_audits" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."customer_merge_audits" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_customer_merge_audits" ON public."customer_merge_audits";
CREATE POLICY "service_role_all_customer_merge_audits"
    ON public."customer_merge_audits"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."customers"
ALTER TABLE public."customers" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."customers" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_customers" ON public."customers";
CREATE POLICY "service_role_all_customers"
    ON public."customers"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."data_retention_policies"
ALTER TABLE public."data_retention_policies" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."data_retention_policies" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_data_retention_policies" ON public."data_retention_policies";
CREATE POLICY "service_role_all_data_retention_policies"
    ON public."data_retention_policies"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."db_connections"
ALTER TABLE public."db_connections" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."db_connections" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_db_connections" ON public."db_connections";
CREATE POLICY "service_role_all_db_connections"
    ON public."db_connections"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."demo_sessions"
ALTER TABLE public."demo_sessions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."demo_sessions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_demo_sessions" ON public."demo_sessions";
CREATE POLICY "service_role_all_demo_sessions"
    ON public."demo_sessions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."document_chunks"
ALTER TABLE public."document_chunks" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."document_chunks" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_document_chunks" ON public."document_chunks";
CREATE POLICY "service_role_all_document_chunks"
    ON public."document_chunks"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."drift_reports"
ALTER TABLE public."drift_reports" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."drift_reports" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_drift_reports" ON public."drift_reports";
CREATE POLICY "service_role_all_drift_reports"
    ON public."drift_reports"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."email_bounces"
ALTER TABLE public."email_bounces" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."email_bounces" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_email_bounces" ON public."email_bounces";
CREATE POLICY "service_role_all_email_bounces"
    ON public."email_bounces"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."email_deliverability_alerts"
ALTER TABLE public."email_deliverability_alerts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."email_deliverability_alerts" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_email_deliverability_alerts" ON public."email_deliverability_alerts";
CREATE POLICY "service_role_all_email_deliverability_alerts"
    ON public."email_deliverability_alerts"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."email_delivery_events"
ALTER TABLE public."email_delivery_events" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."email_delivery_events" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_email_delivery_events" ON public."email_delivery_events";
CREATE POLICY "service_role_all_email_delivery_events"
    ON public."email_delivery_events"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."email_logs"
ALTER TABLE public."email_logs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."email_logs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_email_logs" ON public."email_logs";
CREATE POLICY "service_role_all_email_logs"
    ON public."email_logs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."email_threads"
ALTER TABLE public."email_threads" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."email_threads" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_email_threads" ON public."email_threads";
CREATE POLICY "service_role_all_email_threads"
    ON public."email_threads"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."emergency_states"
ALTER TABLE public."emergency_states" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."emergency_states" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_emergency_states" ON public."emergency_states";
CREATE POLICY "service_role_all_emergency_states"
    ON public."emergency_states"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."erasure_requests"
ALTER TABLE public."erasure_requests" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."erasure_requests" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_erasure_requests" ON public."erasure_requests";
CREATE POLICY "service_role_all_erasure_requests"
    ON public."erasure_requests"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."error_log"
ALTER TABLE public."error_log" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."error_log" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_error_log" ON public."error_log";
CREATE POLICY "service_role_all_error_log"
    ON public."error_log"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."event_buffer"
ALTER TABLE public."event_buffer" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."event_buffer" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_event_buffer" ON public."event_buffer";
CREATE POLICY "service_role_all_event_buffer"
    ON public."event_buffer"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."executed_actions"
ALTER TABLE public."executed_actions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."executed_actions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_executed_actions" ON public."executed_actions";
CREATE POLICY "service_role_all_executed_actions"
    ON public."executed_actions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."feature_flags"
ALTER TABLE public."feature_flags" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."feature_flags" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_feature_flags" ON public."feature_flags";
CREATE POLICY "service_role_all_feature_flags"
    ON public."feature_flags"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."first_victories"
ALTER TABLE public."first_victories" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."first_victories" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_first_victories" ON public."first_victories";
CREATE POLICY "service_role_all_first_victories"
    ON public."first_victories"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."gsd_sessions"
ALTER TABLE public."gsd_sessions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."gsd_sessions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_gsd_sessions" ON public."gsd_sessions";
CREATE POLICY "service_role_all_gsd_sessions"
    ON public."gsd_sessions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."guardrail_blocks"
ALTER TABLE public."guardrail_blocks" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."guardrail_blocks" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_guardrail_blocks" ON public."guardrail_blocks";
CREATE POLICY "service_role_all_guardrail_blocks"
    ON public."guardrail_blocks"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."guardrail_rules"
ALTER TABLE public."guardrail_rules" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."guardrail_rules" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_guardrail_rules" ON public."guardrail_rules";
CREATE POLICY "service_role_all_guardrail_rules"
    ON public."guardrail_rules"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."guardrails_audit_log"
ALTER TABLE public."guardrails_audit_log" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."guardrails_audit_log" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_guardrails_audit_log" ON public."guardrails_audit_log";
CREATE POLICY "service_role_all_guardrails_audit_log"
    ON public."guardrails_audit_log"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."guardrails_blocked_queue"
ALTER TABLE public."guardrails_blocked_queue" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."guardrails_blocked_queue" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_guardrails_blocked_queue" ON public."guardrails_blocked_queue";
CREATE POLICY "service_role_all_guardrails_blocked_queue"
    ON public."guardrails_blocked_queue"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."human_corrections"
ALTER TABLE public."human_corrections" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."human_corrections" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_human_corrections" ON public."human_corrections";
CREATE POLICY "service_role_all_human_corrections"
    ON public."human_corrections"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."idempotency_keys"
ALTER TABLE public."idempotency_keys" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."idempotency_keys" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_idempotency_keys" ON public."idempotency_keys";
CREATE POLICY "service_role_all_idempotency_keys"
    ON public."idempotency_keys"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."identity_match_logs"
ALTER TABLE public."identity_match_logs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."identity_match_logs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_identity_match_logs" ON public."identity_match_logs";
CREATE POLICY "service_role_all_identity_match_logs"
    ON public."identity_match_logs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."inbound_emails"
ALTER TABLE public."inbound_emails" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."inbound_emails" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_inbound_emails" ON public."inbound_emails";
CREATE POLICY "service_role_all_inbound_emails"
    ON public."inbound_emails"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."integrations"
ALTER TABLE public."integrations" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."integrations" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_integrations" ON public."integrations";
CREATE POLICY "service_role_all_integrations"
    ON public."integrations"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."invoices"
ALTER TABLE public."invoices" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."invoices" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_invoices" ON public."invoices";
CREATE POLICY "service_role_all_invoices"
    ON public."invoices"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_action_tickets"
ALTER TABLE public."jarvis_action_tickets" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_action_tickets" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_action_tickets" ON public."jarvis_action_tickets";
CREATE POLICY "service_role_all_jarvis_action_tickets"
    ON public."jarvis_action_tickets"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_activity_events"
ALTER TABLE public."jarvis_activity_events" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_activity_events" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_activity_events" ON public."jarvis_activity_events";
CREATE POLICY "service_role_all_jarvis_activity_events"
    ON public."jarvis_activity_events"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_awareness_snapshots"
ALTER TABLE public."jarvis_awareness_snapshots" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_awareness_snapshots" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_awareness_snapshots" ON public."jarvis_awareness_snapshots";
CREATE POLICY "service_role_all_jarvis_awareness_snapshots"
    ON public."jarvis_awareness_snapshots"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_commands"
ALTER TABLE public."jarvis_commands" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_commands" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_commands" ON public."jarvis_commands";
CREATE POLICY "service_role_all_jarvis_commands"
    ON public."jarvis_commands"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_knowledge_used"
ALTER TABLE public."jarvis_knowledge_used" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_knowledge_used" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_knowledge_used" ON public."jarvis_knowledge_used";
CREATE POLICY "service_role_all_jarvis_knowledge_used"
    ON public."jarvis_knowledge_used"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_messages"
ALTER TABLE public."jarvis_messages" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_messages" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_messages" ON public."jarvis_messages";
CREATE POLICY "service_role_all_jarvis_messages"
    ON public."jarvis_messages"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_proactive_alerts"
ALTER TABLE public."jarvis_proactive_alerts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_proactive_alerts" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_proactive_alerts" ON public."jarvis_proactive_alerts";
CREATE POLICY "service_role_all_jarvis_proactive_alerts"
    ON public."jarvis_proactive_alerts"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."jarvis_sessions"
ALTER TABLE public."jarvis_sessions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."jarvis_sessions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_jarvis_sessions" ON public."jarvis_sessions";
CREATE POLICY "service_role_all_jarvis_sessions"
    ON public."jarvis_sessions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."knowledge_documents"
ALTER TABLE public."knowledge_documents" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."knowledge_documents" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_knowledge_documents" ON public."knowledge_documents";
CREATE POLICY "service_role_all_knowledge_documents"
    ON public."knowledge_documents"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."mcp_connections"
ALTER TABLE public."mcp_connections" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."mcp_connections" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_mcp_connections" ON public."mcp_connections";
CREATE POLICY "service_role_all_mcp_connections"
    ON public."mcp_connections"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."metric_aggregates"
ALTER TABLE public."metric_aggregates" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."metric_aggregates" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_metric_aggregates" ON public."metric_aggregates";
CREATE POLICY "service_role_all_metric_aggregates"
    ON public."metric_aggregates"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."mfa_secrets"
ALTER TABLE public."mfa_secrets" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."mfa_secrets" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_mfa_secrets" ON public."mfa_secrets";
CREATE POLICY "service_role_all_mfa_secrets"
    ON public."mfa_secrets"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."model_usage_logs"
ALTER TABLE public."model_usage_logs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."model_usage_logs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_model_usage_logs" ON public."model_usage_logs";
CREATE POLICY "service_role_all_model_usage_logs"
    ON public."model_usage_logs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."newsletter_subscribers"
ALTER TABLE public."newsletter_subscribers" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."newsletter_subscribers" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_newsletter_subscribers" ON public."newsletter_subscribers";
CREATE POLICY "service_role_all_newsletter_subscribers"
    ON public."newsletter_subscribers"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."notification_logs"
ALTER TABLE public."notification_logs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."notification_logs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_notification_logs" ON public."notification_logs";
CREATE POLICY "service_role_all_notification_logs"
    ON public."notification_logs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."notification_preference_audit"
ALTER TABLE public."notification_preference_audit" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."notification_preference_audit" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_notification_preference_audit" ON public."notification_preference_audit";
CREATE POLICY "service_role_all_notification_preference_audit"
    ON public."notification_preference_audit"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."notification_preferences"
ALTER TABLE public."notification_preferences" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."notification_preferences" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_notification_preferences" ON public."notification_preferences";
CREATE POLICY "service_role_all_notification_preferences"
    ON public."notification_preferences"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."notification_templates"
ALTER TABLE public."notification_templates" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."notification_templates" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_notification_templates" ON public."notification_templates";
CREATE POLICY "service_role_all_notification_templates"
    ON public."notification_templates"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."notifications"
ALTER TABLE public."notifications" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."notifications" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_notifications" ON public."notifications";
CREATE POLICY "service_role_all_notifications"
    ON public."notifications"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."oauth_accounts"
ALTER TABLE public."oauth_accounts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."oauth_accounts" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_oauth_accounts" ON public."oauth_accounts";
CREATE POLICY "service_role_all_oauth_accounts"
    ON public."oauth_accounts"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."onboarding_sessions"
ALTER TABLE public."onboarding_sessions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."onboarding_sessions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_onboarding_sessions" ON public."onboarding_sessions";
CREATE POLICY "service_role_all_onboarding_sessions"
    ON public."onboarding_sessions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ooo_detection_log"
ALTER TABLE public."ooo_detection_log" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ooo_detection_log" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ooo_detection_log" ON public."ooo_detection_log";
CREATE POLICY "service_role_all_ooo_detection_log"
    ON public."ooo_detection_log"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ooo_detection_rules"
ALTER TABLE public."ooo_detection_rules" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ooo_detection_rules" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ooo_detection_rules" ON public."ooo_detection_rules";
CREATE POLICY "service_role_all_ooo_detection_rules"
    ON public."ooo_detection_rules"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ooo_sender_profiles"
ALTER TABLE public."ooo_sender_profiles" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ooo_sender_profiles" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ooo_sender_profiles" ON public."ooo_sender_profiles";
CREATE POLICY "service_role_all_ooo_sender_profiles"
    ON public."ooo_sender_profiles"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."outbound_emails"
ALTER TABLE public."outbound_emails" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."outbound_emails" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_outbound_emails" ON public."outbound_emails";
CREATE POLICY "service_role_all_outbound_emails"
    ON public."outbound_emails"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."outgoing_webhooks"
ALTER TABLE public."outgoing_webhooks" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."outgoing_webhooks" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_outgoing_webhooks" ON public."outgoing_webhooks";
CREATE POLICY "service_role_all_outgoing_webhooks"
    ON public."outgoing_webhooks"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."overage_charges"
ALTER TABLE public."overage_charges" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."overage_charges" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_overage_charges" ON public."overage_charges";
CREATE POLICY "service_role_all_overage_charges"
    ON public."overage_charges"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."paddle_reconciliation_reports"
ALTER TABLE public."paddle_reconciliation_reports" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."paddle_reconciliation_reports" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_paddle_reconciliation_reports" ON public."paddle_reconciliation_reports";
CREATE POLICY "service_role_all_paddle_reconciliation_reports"
    ON public."paddle_reconciliation_reports"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."paddle_webhook_events"
ALTER TABLE public."paddle_webhook_events" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."paddle_webhook_events" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_paddle_webhook_events" ON public."paddle_webhook_events";
CREATE POLICY "service_role_all_paddle_webhook_events"
    ON public."paddle_webhook_events"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."password_reset_tokens"
ALTER TABLE public."password_reset_tokens" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."password_reset_tokens" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_password_reset_tokens" ON public."password_reset_tokens";
CREATE POLICY "service_role_all_password_reset_tokens"
    ON public."password_reset_tokens"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."payment_failures"
ALTER TABLE public."payment_failures" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."payment_failures" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_payment_failures" ON public."payment_failures";
CREATE POLICY "service_role_all_payment_failures"
    ON public."payment_failures"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."payment_methods"
ALTER TABLE public."payment_methods" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."payment_methods" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_payment_methods" ON public."payment_methods";
CREATE POLICY "service_role_all_payment_methods"
    ON public."payment_methods"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."phone_otps"
ALTER TABLE public."phone_otps" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."phone_otps" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_phone_otps" ON public."phone_otps";
CREATE POLICY "service_role_all_phone_otps"
    ON public."phone_otps"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."pipeline_state_snapshots"
ALTER TABLE public."pipeline_state_snapshots" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."pipeline_state_snapshots" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_pipeline_state_snapshots" ON public."pipeline_state_snapshots";
CREATE POLICY "service_role_all_pipeline_state_snapshots"
    ON public."pipeline_state_snapshots"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."prompt_injection_attempts"
ALTER TABLE public."prompt_injection_attempts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."prompt_injection_attempts" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_prompt_injection_attempts" ON public."prompt_injection_attempts";
CREATE POLICY "service_role_all_prompt_injection_attempts"
    ON public."prompt_injection_attempts"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."prompt_templates"
ALTER TABLE public."prompt_templates" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."prompt_templates" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_prompt_templates" ON public."prompt_templates";
CREATE POLICY "service_role_all_prompt_templates"
    ON public."prompt_templates"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."proration_audits"
ALTER TABLE public."proration_audits" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."proration_audits" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_proration_audits" ON public."proration_audits";
CREATE POLICY "service_role_all_proration_audits"
    ON public."proration_audits"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."qa_scores"
ALTER TABLE public."qa_scores" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."qa_scores" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_qa_scores" ON public."qa_scores";
CREATE POLICY "service_role_all_qa_scores"
    ON public."qa_scores"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."rate_limit_counters"
ALTER TABLE public."rate_limit_counters" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."rate_limit_counters" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_rate_limit_counters" ON public."rate_limit_counters";
CREATE POLICY "service_role_all_rate_limit_counters"
    ON public."rate_limit_counters"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."rate_limit_events"
ALTER TABLE public."rate_limit_events" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."rate_limit_events" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_rate_limit_events" ON public."rate_limit_events";
CREATE POLICY "service_role_all_rate_limit_events"
    ON public."rate_limit_events"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."refresh_tokens"
ALTER TABLE public."refresh_tokens" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."refresh_tokens" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_refresh_tokens" ON public."refresh_tokens";
CREATE POLICY "service_role_all_refresh_tokens"
    ON public."refresh_tokens"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."response_templates"
ALTER TABLE public."response_templates" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."response_templates" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_response_templates" ON public."response_templates";
CREATE POLICY "service_role_all_response_templates"
    ON public."response_templates"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."rest_connectors"
ALTER TABLE public."rest_connectors" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."rest_connectors" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_rest_connectors" ON public."rest_connectors";
CREATE POLICY "service_role_all_rest_connectors"
    ON public."rest_connectors"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."roi_snapshots"
ALTER TABLE public."roi_snapshots" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."roi_snapshots" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_roi_snapshots" ON public."roi_snapshots";
CREATE POLICY "service_role_all_roi_snapshots"
    ON public."roi_snapshots"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."service_configs"
ALTER TABLE public."service_configs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."service_configs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_service_configs" ON public."service_configs";
CREATE POLICY "service_role_all_service_configs"
    ON public."service_configs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."shadow_mode_configs"
ALTER TABLE public."shadow_mode_configs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."shadow_mode_configs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_shadow_mode_configs" ON public."shadow_mode_configs";
CREATE POLICY "service_role_all_shadow_mode_configs"
    ON public."shadow_mode_configs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."shadow_mode_results"
ALTER TABLE public."shadow_mode_results" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."shadow_mode_results" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_shadow_mode_results" ON public."shadow_mode_results";
CREATE POLICY "service_role_all_shadow_mode_results"
    ON public."shadow_mode_results"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."sla_policies"
ALTER TABLE public."sla_policies" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."sla_policies" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_sla_policies" ON public."sla_policies";
CREATE POLICY "service_role_all_sla_policies"
    ON public."sla_policies"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."sla_timers"
ALTER TABLE public."sla_timers" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."sla_timers" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_sla_timers" ON public."sla_timers";
CREATE POLICY "service_role_all_sla_timers"
    ON public."sla_timers"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."sms_channel_configs"
ALTER TABLE public."sms_channel_configs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."sms_channel_configs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_sms_channel_configs" ON public."sms_channel_configs";
CREATE POLICY "service_role_all_sms_channel_configs"
    ON public."sms_channel_configs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."sms_conversations"
ALTER TABLE public."sms_conversations" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."sms_conversations" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_sms_conversations" ON public."sms_conversations";
CREATE POLICY "service_role_all_sms_conversations"
    ON public."sms_conversations"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."sms_messages"
ALTER TABLE public."sms_messages" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."sms_messages" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_sms_messages" ON public."sms_messages";
CREATE POLICY "service_role_all_sms_messages"
    ON public."sms_messages"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."subscriptions"
ALTER TABLE public."subscriptions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."subscriptions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_subscriptions" ON public."subscriptions";
CREATE POLICY "service_role_all_subscriptions"
    ON public."subscriptions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."technique_caches"
ALTER TABLE public."technique_caches" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."technique_caches" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_technique_caches" ON public."technique_caches";
CREATE POLICY "service_role_all_technique_caches"
    ON public."technique_caches"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."technique_configurations"
ALTER TABLE public."technique_configurations" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."technique_configurations" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_technique_configurations" ON public."technique_configurations";
CREATE POLICY "service_role_all_technique_configurations"
    ON public."technique_configurations"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."technique_executions"
ALTER TABLE public."technique_executions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."technique_executions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_technique_executions" ON public."technique_executions";
CREATE POLICY "service_role_all_technique_executions"
    ON public."technique_executions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."technique_versions"
ALTER TABLE public."technique_versions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."technique_versions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_technique_versions" ON public."technique_versions";
CREATE POLICY "service_role_all_technique_versions"
    ON public."technique_versions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_assignments"
ALTER TABLE public."ticket_assignments" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_assignments" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_assignments" ON public."ticket_assignments";
CREATE POLICY "service_role_all_ticket_assignments"
    ON public."ticket_assignments"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_attachments"
ALTER TABLE public."ticket_attachments" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_attachments" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_attachments" ON public."ticket_attachments";
CREATE POLICY "service_role_all_ticket_attachments"
    ON public."ticket_attachments"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_collisions"
ALTER TABLE public."ticket_collisions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_collisions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_collisions" ON public."ticket_collisions";
CREATE POLICY "service_role_all_ticket_collisions"
    ON public."ticket_collisions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_feedbacks"
ALTER TABLE public."ticket_feedbacks" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_feedbacks" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_feedbacks" ON public."ticket_feedbacks";
CREATE POLICY "service_role_all_ticket_feedbacks"
    ON public."ticket_feedbacks"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_intents"
ALTER TABLE public."ticket_intents" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_intents" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_intents" ON public."ticket_intents";
CREATE POLICY "service_role_all_ticket_intents"
    ON public."ticket_intents"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_internal_notes"
ALTER TABLE public."ticket_internal_notes" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_internal_notes" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_internal_notes" ON public."ticket_internal_notes";
CREATE POLICY "service_role_all_ticket_internal_notes"
    ON public."ticket_internal_notes"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_merges"
ALTER TABLE public."ticket_merges" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_merges" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_merges" ON public."ticket_merges";
CREATE POLICY "service_role_all_ticket_merges"
    ON public."ticket_merges"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_messages"
ALTER TABLE public."ticket_messages" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_messages" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_messages" ON public."ticket_messages";
CREATE POLICY "service_role_all_ticket_messages"
    ON public."ticket_messages"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_status_changes"
ALTER TABLE public."ticket_status_changes" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_status_changes" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_status_changes" ON public."ticket_status_changes";
CREATE POLICY "service_role_all_ticket_status_changes"
    ON public."ticket_status_changes"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."ticket_triggers"
ALTER TABLE public."ticket_triggers" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."ticket_triggers" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_ticket_triggers" ON public."ticket_triggers";
CREATE POLICY "service_role_all_ticket_triggers"
    ON public."ticket_triggers"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."tickets"
ALTER TABLE public."tickets" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."tickets" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_tickets" ON public."tickets";
CREATE POLICY "service_role_all_tickets"
    ON public."tickets"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."training_checkpoints"
ALTER TABLE public."training_checkpoints" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."training_checkpoints" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_training_checkpoints" ON public."training_checkpoints";
CREATE POLICY "service_role_all_training_checkpoints"
    ON public."training_checkpoints"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."training_datasets"
ALTER TABLE public."training_datasets" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."training_datasets" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_training_datasets" ON public."training_datasets";
CREATE POLICY "service_role_all_training_datasets"
    ON public."training_datasets"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."training_runs"
ALTER TABLE public."training_runs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."training_runs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_training_runs" ON public."training_runs";
CREATE POLICY "service_role_all_training_runs"
    ON public."training_runs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."transactions"
ALTER TABLE public."transactions" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."transactions" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_transactions" ON public."transactions";
CREATE POLICY "service_role_all_transactions"
    ON public."transactions"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."undo_log"
ALTER TABLE public."undo_log" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."undo_log" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_undo_log" ON public."undo_log";
CREATE POLICY "service_role_all_undo_log"
    ON public."undo_log"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."usage_records"
ALTER TABLE public."usage_records" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."usage_records" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_usage_records" ON public."usage_records";
CREATE POLICY "service_role_all_usage_records"
    ON public."usage_records"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."user_details"
ALTER TABLE public."user_details" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."user_details" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_user_details" ON public."user_details";
CREATE POLICY "service_role_all_user_details"
    ON public."user_details"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."user_notification_preferences"
ALTER TABLE public."user_notification_preferences" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."user_notification_preferences" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_user_notification_preferences" ON public."user_notification_preferences";
CREATE POLICY "service_role_all_user_notification_preferences"
    ON public."user_notification_preferences"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."users"
ALTER TABLE public."users" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."users" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_users" ON public."users";
CREATE POLICY "service_role_all_users"
    ON public."users"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."variant_ai_capabilities"
ALTER TABLE public."variant_ai_capabilities" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."variant_ai_capabilities" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_variant_ai_capabilities" ON public."variant_ai_capabilities";
CREATE POLICY "service_role_all_variant_ai_capabilities"
    ON public."variant_ai_capabilities"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."variant_instances"
ALTER TABLE public."variant_instances" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."variant_instances" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_variant_instances" ON public."variant_instances";
CREATE POLICY "service_role_all_variant_instances"
    ON public."variant_instances"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."variant_limits"
ALTER TABLE public."variant_limits" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."variant_limits" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_variant_limits" ON public."variant_limits";
CREATE POLICY "service_role_all_variant_limits"
    ON public."variant_limits"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."variant_workload_distribution"
ALTER TABLE public."variant_workload_distribution" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."variant_workload_distribution" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_variant_workload_distribution" ON public."variant_workload_distribution";
CREATE POLICY "service_role_all_variant_workload_distribution"
    ON public."variant_workload_distribution"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."verification_tokens"
ALTER TABLE public."verification_tokens" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."verification_tokens" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_verification_tokens" ON public."verification_tokens";
CREATE POLICY "service_role_all_verification_tokens"
    ON public."verification_tokens"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."voice_calls"
ALTER TABLE public."voice_calls" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."voice_calls" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_voice_calls" ON public."voice_calls";
CREATE POLICY "service_role_all_voice_calls"
    ON public."voice_calls"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."voice_channel_configs"
ALTER TABLE public."voice_channel_configs" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."voice_channel_configs" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_voice_channel_configs" ON public."voice_channel_configs";
CREATE POLICY "service_role_all_voice_channel_configs"
    ON public."voice_channel_configs"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."voice_conversations"
ALTER TABLE public."voice_conversations" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."voice_conversations" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_voice_conversations" ON public."voice_conversations";
CREATE POLICY "service_role_all_voice_conversations"
    ON public."voice_conversations"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."webhook_events"
ALTER TABLE public."webhook_events" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."webhook_events" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_webhook_events" ON public."webhook_events";
CREATE POLICY "service_role_all_webhook_events"
    ON public."webhook_events"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."webhook_integrations"
ALTER TABLE public."webhook_integrations" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."webhook_integrations" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_webhook_integrations" ON public."webhook_integrations";
CREATE POLICY "service_role_all_webhook_integrations"
    ON public."webhook_integrations"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Table: public."webhook_sequences"
ALTER TABLE public."webhook_sequences" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."webhook_sequences" FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_webhook_sequences" ON public."webhook_sequences";
CREATE POLICY "service_role_all_webhook_sequences"
    ON public."webhook_sequences"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMIT;

-- Verification queries (run after migration):
-- SELECT count(*) FROM pg_tables t JOIN pg_class c ON c.relname=t.tablename
--   WHERE t.schemaname='public' AND c.relrowsecurity=true;
-- SELECT count(*) FROM pg_policies WHERE schemaname='public' AND policyname LIKE 'service_role_all_%';
