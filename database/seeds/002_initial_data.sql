-- ══════════════════════════════════════════════════════════════════
-- PARWA — Initial Seed Data
-- Default variant and technique configurations, SLA policies,
-- channel configs, tier limits, and brand voice templates.
-- ══════════════════════════════════════════════════════════════════

-- ── Default SLA Policies (per plan tier × priority) ────────────────
-- These are global defaults; each company gets copies on signup.
-- Inserted only if the sla_policies table exists and is empty.

DO $$
DECLARE
    _company_id TEXT;
    _plan_tier TEXT;
    _priority TEXT;
    _first_resp INTEGER;
    _resolution INTEGER;
    _update_freq INTEGER;
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sla_policies') THEN
        IF NOT EXISTS (SELECT 1 FROM sla_policies LIMIT 1) THEN

            -- Use a sentinel company_id for global defaults.
            -- Real companies get copies via onboarding migration.
            _company_id := '00000000-0000-0000-0000-000000000000';

            FOR _plan_tier, _priority, _first_resp, _resolution, _update_freq IN
                VALUES
                -- Mini (starter) plan
                ('mini',    'critical', 15,  120, 30),
                ('mini',    'high',     30,  240, 60),
                ('mini',    'medium',   60,  480, 120),
                ('mini',    'low',      120, 1440, 240),

                -- Pro (growth) plan
                ('pro',     'critical', 5,   60,  15),
                ('pro',     'high',     15,  120, 30),
                ('pro',     'medium',   30,  240, 60),
                ('pro',     'low',      60,  480, 120),

                -- High (enterprise) plan
                ('high',    'critical', 2,   30,  10),
                ('high',    'high',     5,   60,  15),
                ('high',    'medium',   15,  120, 30),
                ('high',    'low',      30,  240, 60)
            LOOP
                INSERT INTO sla_policies (
                    id, company_id, plan_tier, priority,
                    first_response_minutes, resolution_minutes,
                    update_frequency_minutes, is_active,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text, _company_id,
                    _plan_tier, _priority,
                    _first_resp, _resolution, _update_freq,
                    true,
                    now(), now()
                );
            END LOOP;
        END IF;
    END IF;
END $$;


-- ── Default Variant Limits (per tier) ──────────────────────────────
-- Stored as ai_token_budgets with variant_default_limits JSON.
-- These set daily token budgets per variant tier.

DO $$
DECLARE
    _company_id TEXT;
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ai_token_budgets') THEN
        IF NOT EXISTS (SELECT 1 FROM ai_token_budgets WHERE budget_type = 'daily' LIMIT 1) THEN

            _company_id := '00000000-0000-0000-0000-000000000000';

            -- Mini PARWA daily budget
            INSERT INTO ai_token_budgets (
                id, company_id, instance_id,
                budget_type, budget_period,
                max_tokens, used_tokens,
                alert_threshold_pct, alert_sent, hard_stop,
                status, variant_default_limits,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid()::text, _company_id, NULL,
                'daily', to_char(now(), 'YYYY-MM-DD'),
                500000, 0,
                80, false, true,
                'active',
                '{"mini_parwa": {"daily": 500000, "monthly": 15000000}, "parwa": {"daily": 2000000, "monthly": 60000000}, "parwa_high": {"daily": 10000000, "monthly": 300000000}}',
                now(), now()
            );

            -- PARWA Standard daily budget
            INSERT INTO ai_token_budgets (
                id, company_id, instance_id,
                budget_type, budget_period,
                max_tokens, used_tokens,
                alert_threshold_pct, alert_sent, hard_stop,
                status, variant_default_limits,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid()::text, _company_id, NULL,
                'daily', to_char(now(), 'YYYY-MM-DD'),
                2000000, 0,
                80, false, true,
                'active',
                '{"mini_parwa": {"daily": 500000, "monthly": 15000000}, "parwa": {"daily": 2000000, "monthly": 60000000}, "parwa_high": {"daily": 10000000, "monthly": 300000000}}',
                now(), now()
            );

            -- PARWA High daily budget
            INSERT INTO ai_token_budgets (
                id, company_id, instance_id,
                budget_type, budget_period,
                max_tokens, used_tokens,
                alert_threshold_pct, alert_sent, hard_stop,
                status, variant_default_limits,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid()::text, _company_id, NULL,
                'daily', to_char(now(), 'YYYY-MM-DD'),
                10000000, 0,
                80, false, true,
                'active',
                '{"mini_parwa": {"daily": 500000, "monthly": 15000000}, "parwa": {"daily": 2000000, "monthly": 60000000}, "parwa_high": {"daily": 10000000, "monthly": 300000000}}',
                now(), now()
            );
        END IF;
    END IF;
END $$;


-- ── Default Channel Configurations ─────────────────────────────────
-- Seed the channels table with the five supported channel types
-- and default per-company channel_configs.

DO $$
BEGIN
    -- Seed global channel definitions (no company_id — these are system-wide)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'channels') THEN
        IF NOT EXISTS (SELECT 1 FROM channels LIMIT 1) THEN
            INSERT INTO channels (id, name, channel_type, description, is_active, created_at) VALUES
                (gen_random_uuid()::text, 'Email',  'email',  'Email channel for inbound/outbound support', true, now()),
                (gen_random_uuid()::text, 'Chat',   'chat',   'Live chat widget for real-time support',     true, now()),
                (gen_random_uuid()::text, 'SMS',    'sms',    'SMS/text messaging channel',                 true, now()),
                (gen_random_uuid()::text, 'Voice',  'voice',  'Voice/telephony channel',                    true, now()),
                (gen_random_uuid()::text, 'Social', 'social', 'Social media messaging (Twitter, WhatsApp)', true, now());
        END IF;
    END IF;

    -- Seed default per-company channel configs
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'channel_configs') THEN
        IF NOT EXISTS (SELECT 1 FROM channel_configs LIMIT 1) THEN
            DECLARE
                _default_company_id TEXT := '00000000-0000-0000-0000-000000000000';
            BEGIN
                INSERT INTO channel_configs (id, company_id, channel_type, is_enabled, config_json, auto_create_ticket, char_limit, allowed_file_types, max_file_size, created_at, updated_at) VALUES
                    (gen_random_uuid()::text, _default_company_id, 'email',  true,  '{"smtp_host": "", "imap_host": "", "from_address": ""}',        true, 50000, '["pdf","doc","docx","jpg","png","csv"]', 10485760, now(), now()),
                    (gen_random_uuid()::text, _default_company_id, 'chat',   true,  '{"widget_color": "#f97316", "position": "bottom-right"}',       true, 4000,  '["jpg","png","gif","pdf"]',               5242880,  now(), now()),
                    (gen_random_uuid()::text, _default_company_id, 'sms',    false, '{"twilio_phone": "", "webhook_url": ""}',                     true, 320,   '[]',                                      0,        now(), now()),
                    (gen_random_uuid()::text, _default_company_id, 'voice',  false, '{"twilio_phone": "", "ivr_enabled": false}',                  true, NULL,  '[]',                                      0,        now(), now()),
                    (gen_random_uuid()::text, _default_company_id, 'social', false, '{"twitter_handle": "", "whatsapp_number": ""}',               true, 280,   '["jpg","png","gif"]',                     5242880,  now(), now());
            END;
        END IF;
    END IF;
END $$;


-- ── Default Technique Configurations per Tier ──────────────────────
-- Tier 1 techniques (always on, not in this table) + Tier 2/3 per plan.

DO $$
DECLARE
    _company_id TEXT;
    _techniques_tier2 TEXT[] := ARRAY[
        'cot', 'react', 'crp', 'self_consistency', 'reflexion',
        'step_back', 'least_to_most', 'gst'
    ];
    _techniques_tier3 TEXT[] := ARRAY[
        'tot', 'thot', 'uot', 'reverse_thinking',
        'metacognition', 'socratic', 'analogical',
        'abduction', 'dialectical', 'counterfactual',
        'ensemble_reasoning', 'adaptive_prompting'
    ];
    _tech_id TEXT;
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'technique_configurations') THEN
        IF NOT EXISTS (SELECT 1 FROM technique_configurations LIMIT 1) THEN

            _company_id := '00000000-0000-0000-0000-000000000000';

            -- Tier 2 techniques: enabled for pro and high plans
            FOREACH _tech_id IN ARRAY _techniques_tier2 LOOP
                INSERT INTO technique_configurations (
                    id, company_id, technique_id, tier,
                    is_enabled, custom_token_budget,
                    custom_trigger_threshold, custom_timeout_ms,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text, _company_id, _tech_id, 'tier_2',
                    true, NULL, NULL, NULL,
                    now(), now()
                );
            END LOOP;

            -- Tier 3 techniques: enabled only for high plan
            FOREACH _tech_id IN ARRAY _techniques_tier3 LOOP
                INSERT INTO technique_configurations (
                    id, company_id, technique_id, tier,
                    is_enabled, custom_token_budget,
                    custom_trigger_threshold, custom_timeout_ms,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text, _company_id, _tech_id, 'tier_3',
                    true, NULL, NULL, NULL,
                    now(), now()
                );
            END LOOP;
        END IF;
    END IF;
END $$;


-- ── Default Brand Voice Template ───────────────────────────────────
-- Stored in company_settings as the default brand voice for new tenants.

DO $$
DECLARE
    _company_id TEXT;
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'company_settings') THEN
        IF NOT EXISTS (SELECT 1 FROM company_settings LIMIT 1) THEN

            _company_id := '00000000-0000-0000-0000-000000000000';

            INSERT INTO company_settings (
                id, company_id,
                ooo_status, ooo_message, ooo_until,
                brand_voice,
                tone_guidelines,
                prohibited_phrases,
                pii_patterns,
                custom_regex,
                top_k,
                similarity_threshold,
                rerank_model,
                confidence_thresholds,
                intent_labels,
                custom_rules,
                assignment_rules,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid()::text, _company_id,
                'inactive', NULL, NULL,
                'Our brand voice is helpful, clear, and professional. We address customers by their first name when known. We prioritize solving problems quickly while being empathetic to their situation.',
                '["Be concise and direct", "Use active voice", "Avoid jargon unless the customer uses it first", "Show empathy before offering solutions", "End with a clear next step or question"]',
                '["I don''t know", "That''s not my job", "You have to", "You must", "Calm down", "As I said before"]',
                '["email", "phone", "ssn", "credit_card", "api_key", "password", "token"]',
                '[]',
                5,
                0.70,
                NULL,
                '{"high": 0.85, "medium": 0.65, "low": 0.45}',
                '["refund", "technical", "billing", "complaint", "feature_request", "general", "shipping", "cancellation"]',
                '[]',
                '[]',
                now(), now()
            );
        END IF;
    END IF;
END $$;
