-- ════════════════════════════════════════════════════════════════
-- PARWA — Sample Tickets & Customers Seed Data
-- Week 2 Day 4 (Agent 3 Task)
-- ════════════════════════════════════════════════════════════════

DO $$
DECLARE
    -- Tenant IDs
    v_tenant_standard UUID;
    
    -- Customer IDs
    v_cust_1 UUID := gen_random_uuid();
    v_cust_2 UUID := gen_random_uuid();
    
    -- Session IDs
    v_sess_1 UUID := gen_random_uuid();
    
    -- Interaction IDs
    v_interact_1 UUID := gen_random_uuid();
    v_interact_2 UUID := gen_random_uuid();

    -- Ticket IDs
    v_ticket_1 UUID := gen_random_uuid();
    v_ticket_2 UUID := gen_random_uuid();

    -- User/Agent IDs
    v_agent_id UUID;

BEGIN
    -- 1. Grab the "standard" tenant inserted by Agent 2 in clients.sql
    SELECT id INTO v_tenant_standard FROM tenants WHERE plan = 'parwa' LIMIT 1;

    -- If the tenant doesn't exist, we skip insertion to avoid FK errors 
    -- (in a real test runner, clients.sql runs first)
    IF v_tenant_standard IS NULL THEN
        RAISE NOTICE 'Skipping sample_tickets seed: Standard tenant not found. Run clients.sql first.';
        RETURN;
    END IF;

    -- Grab an agent user from that tenant
    SELECT id INTO v_agent_id FROM users WHERE tenant_id = v_tenant_standard AND role = 'agent' LIMIT 1;

    -- 2. Insert Mock Customers
    INSERT INTO customers (id, tenant_id, external_id, email, phone, name)
    VALUES 
        (v_cust_1, v_tenant_standard, 'cus_live_991', 'john.doe@example.com', '+15550100', 'John Doe'),
        (v_cust_2, v_tenant_standard, 'cus_live_992', 'jane.smith@example.com', '+15550200', 'Jane Smith')
    ON CONFLICT (tenant_id, external_id) DO NOTHING;

    -- 3. Insert Mock Sessions and Interactions for the Agent Lightning loop
    INSERT INTO sessions (id, tenant_id, customer_id, channel, status)
    VALUES 
        (v_sess_1, v_tenant_standard, v_cust_1, 'chat', 'closed')
    ON CONFLICT DO NOTHING;

    INSERT INTO interactions (id, session_id, role, content, model_used, tokens_prompt, tokens_completion)
    VALUES 
        (v_interact_1, v_sess_1, 'user', 'Where is my order? It was supposed to arrive yesterday.', NULL, 12, 0),
        (v_interact_2, v_sess_1, 'assistant', 'I apologize for the delay. Your order is currently delayed in transit.', 'gpt-4o-mini', 150, 45)
    ON CONFLICT DO NOTHING;

    -- 4. Insert Mock Support Tickets
    INSERT INTO support_tickets (id, tenant_id, customer_id, channel, status, sentiment, assigned_to)
    VALUES 
        (v_ticket_1, v_tenant_standard, v_cust_1, 'chat', 'resolved', 'negative', v_agent_id),
        (v_ticket_2, v_tenant_standard, v_cust_2, 'email', 'open', 'neutral', NULL)
    ON CONFLICT DO NOTHING;

    -- 5. Insert Mock Human Correction (Agent Lightning requirement)
    -- This correction is marked 'exported_for_training = FALSE' so the background worker can pick it up.
    INSERT INTO human_corrections (
        tenant_id, 
        ticket_id, 
        interaction_id,
        corrected_by_user_id, 
        original_prompt, 
        ai_draft_response, 
        human_approved_response, 
        outcome,
        exported_for_training
    )
    VALUES (
        v_tenant_standard,
        v_ticket_1,
        v_interact_2,
        v_agent_id,
        'Where is my order? It was supposed to arrive yesterday.',
        'I apologize for the delay. Your order is currently delayed in transit.',
        'Hi John, I am so sorry about that! I checked with FedEx and it got held up at the local hub. It is out for delivery today and I refunded your shipping cost for the trouble.',
        'rejected', -- AI response was rejected by the human agent and rewritten
        FALSE
    );

    RAISE NOTICE 'Sample tickets, customers, and human corrections seeded successfully for tenant %.', v_tenant_standard;

END $$;
