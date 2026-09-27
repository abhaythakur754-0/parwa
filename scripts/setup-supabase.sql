-- ═══════════════════════════════════════════════════════════════
-- PARWA FLEXPAY - SUPABASE DATABASE SETUP SCRIPT
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql
-- ═══════════════════════════════════════════════════════════════

-- ── 1. ONBOARDING SESSIONS ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_sessions (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    current_step INTEGER NOT NULL DEFAULT 1,
    completed_steps INTEGER[] DEFAULT '{}',
    details_completed BOOLEAN DEFAULT false,
    integration_completed BOOLEAN DEFAULT false,
    kb_completed BOOLEAN DEFAULT false,
    first_victory_completed BOOLEAN DEFAULT false,
    ai_name TEXT DEFAULT 'Jarvis',
    ai_tone TEXT DEFAULT 'professional',
    ai_greeting TEXT,
    selected_variant TEXT,
    selected_industry TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_onboarding_user_id ON onboarding_sessions(user_id);

-- ── 2. USER DETAILS (Step 1 Data) ────────────────────────────────
CREATE TABLE IF NOT EXISTS user_details (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    company_name TEXT,
    company_url TEXT,
    work_email TEXT,
    work_email_verified BOOLEAN DEFAULT false,
    industry TEXT,
    company_size TEXT,
    website TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ── 3. LEGAL CONSENTS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS legal_consents (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_details_id TEXT NOT NULL,
    consent_type TEXT NOT NULL,
    accepted_at TIMESTAMPTZ DEFAULT now(),
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_legal_consents ON legal_consents(user_details_id, consent_type);

-- ── 4. INTEGRATIONS (Step 2) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS integrations (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    config JSONB DEFAULT '{}',
    kb_connected_id TEXT,
    last_test_at TIMESTAMPTZ,
    last_test_result TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_integrations_user ON integrations(user_id, type);

-- ── 5. KNOWLEDGE BASES ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT DEFAULT 'uploaded',
    source_url TEXT,
    crm_type TEXT,
    status TEXT DEFAULT 'pending',
    document_count INTEGER DEFAULT 0,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_user ON knowledge_bases(user_id);

-- ── 6. KNOWLEDGE DOCUMENTS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    kb_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    chunk_count INTEGER,
    error_message TEXT,
    external_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_docs_kb ON knowledge_documents(kb_id, status);

-- ── 7. PAYMENTS (FlexPay/Razorpay) ───────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL,
    subscription_id TEXT,
    amount INTEGER NOT NULL,
    currency TEXT DEFAULT 'INR',
    status TEXT DEFAULT 'pending',
    payment_method TEXT,
    razorpay_order_id TEXT,
    razorpay_payment_id TEXT,
    razorpay_signature TEXT,
    installment_number INTEGER,
    total_installments INTEGER,
    receipt_url TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id, status);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(razorpay_order_id);

-- ── 8. SUBSCRIPTIONS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    billing_cycle TEXT DEFAULT 'monthly',
    amount INTEGER NOT NULL,
    currency TEXT DEFAULT 'INR',
    start_date TIMESTAMPTZ DEFAULT now(),
    end_date TIMESTAMPTZ,
    trial_ends_at TIMESTAMPTZ,
    kb_included BOOLEAN DEFAULT true,
    max_documents INTEGER DEFAULT 100,
    current_period_start TIMESTAMPTZ DEFAULT now(),
    current_period_end TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id, status);

-- ── 9. ENABLE ROW LEVEL SECURITY (RLS) ────────────────────────────
ALTER TABLE onboarding_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_details ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- ── 10. CREATE POLICIES (Service role has full access) ─────────────
-- These policies allow authenticated users to manage their own data

CREATE POLICY "Users can view own onboarding" ON onboarding_sessions
    FOR SELECT USING (auth.uid()::text = user_id);
    
CREATE POLICY "Users can insert own onboarding" ON onboarding_sessions
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);
    
CREATE POLICY "Users can update own onboarding" ON onboarding_sessions
    FOR UPDATE USING (auth.uid()::text = user_id);

-- Similar policies for other tables...
CREATE POLICY "Users can view own details" ON user_details
    FOR SELECT USING (auth.uid()::text = user_id);
    
CREATE POLICY "Users can insert own details" ON user_details
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);
    
CREATE POLICY "Users can update own details" ON user_details
    FOR UPDATE USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own integrations" ON integrations
    FOR SELECT USING (auth.uid()::text = user_id);
    
CREATE POLICY "Users can manage own integrations" ON integrations
    FOR ALL USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own KB" ON knowledge_bases
    FOR SELECT USING (auth.uid()::text = user_id);
    
CREATE POLICY "Users can manage own KB" ON knowledge_bases
    FOR ALL USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own docs" ON knowledge_documents
    FOR SELECT USING (auth.uid()::text = user_id);
    
CREATE POLICY "Users can manage own docs" ON knowledge_documents
    FOR ALL USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own payments" ON payments
    FOR SELECT USING (auth.uid()::text = user_id);
    
CREATE POLICY "Users can insert own payments" ON payments
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Users can view own subscriptions" ON subscriptions
    FOR SELECT USING (auth.uid()::text = user_id);

-- ═══════════════════════════════════════════════════════════════
-- ✅ DATABASE SETUP COMPLETE!
-- Tables created: onboarding_sessions, user_details, legal_consents,
--                  integrations, knowledge_bases, knowledge_documents,
--                  payments, subscriptions
-- ═══════════════════════════════════════════════════════════════
