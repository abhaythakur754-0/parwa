-- ═══════════════════════════════════════════════════════════════════════════════
-- PARWA — Ticket Table Indexes
-- Week 26 Day 1 (Builder 1 Task)
-- Target: Query time < 10ms for indexed queries
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- Support Tickets Table Indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Index 1: Primary tenant isolation index
-- Purpose: Fast filtering of tickets by company for multi-tenant isolation
-- Query: SELECT * FROM support_tickets WHERE company_id = ?
CREATE INDEX IF NOT EXISTS idx_tickets_company_id
ON support_tickets(company_id);

-- Index 2: Status filtering index
-- Purpose: Fast filtering by ticket status (open, pending_approval, resolved, escalated)
-- Query: SELECT * FROM support_tickets WHERE status = 'open'
CREATE INDEX IF NOT EXISTS idx_tickets_status
ON support_tickets(status);

-- Index 3: Time-based queries index
-- Purpose: Fast sorting and filtering by creation date
-- Query: SELECT * FROM support_tickets ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_tickets_created_at
ON support_tickets(created_at DESC);

-- Index 4: Composite index for common query pattern
-- Purpose: Optimize the most frequent query: tickets by company + status + time
-- Query: SELECT * FROM support_tickets WHERE company_id = ? AND status = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_tickets_company_status_created
ON support_tickets(company_id, status, created_at DESC);

-- Index 5: Priority sorting index
-- Purpose: Fast sorting and filtering by priority for queue management
-- Query: SELECT * FROM support_tickets WHERE company_id = ? ORDER BY priority DESC
CREATE INDEX IF NOT EXISTS idx_tickets_priority
ON support_tickets(company_id, ai_confidence DESC);

-- Index 6: Channel filtering index
-- Purpose: Fast filtering by communication channel (chat, email, sms, voice)
-- Query: SELECT * FROM support_tickets WHERE channel = 'chat'
CREATE INDEX IF NOT EXISTS idx_tickets_channel
ON support_tickets(channel);

-- Index 7: Customer email lookup index
-- Purpose: Fast lookup of tickets by customer email
-- Query: SELECT * FROM support_tickets WHERE customer_email = ?
CREATE INDEX IF NOT EXISTS idx_tickets_customer_email
ON support_tickets(company_id, customer_email);

-- Index 8: Category filtering index
-- Purpose: Fast filtering by ticket category
-- Query: SELECT * FROM support_tickets WHERE category = 'refund'
CREATE INDEX IF NOT EXISTS idx_tickets_category
ON support_tickets(company_id, category);

-- Index 9: Assigned agent index
-- Purpose: Fast lookup of tickets assigned to specific agents
-- Query: SELECT * FROM support_tickets WHERE assigned_to = ?
CREATE INDEX IF NOT EXISTS idx_tickets_assigned
ON support_tickets(company_id, assigned_to)
WHERE assigned_to IS NOT NULL;

-- Index 10: Partial index for pending approvals
-- Purpose: Fast lookup of tickets pending approval (critical for approval queue)
-- Query: SELECT * FROM support_tickets WHERE status = 'pending_approval'
CREATE INDEX IF NOT EXISTS idx_tickets_pending_approval
ON support_tickets(company_id, created_at DESC)
WHERE status = 'pending_approval';

-- Index 11: Resolved tickets index
-- Purpose: Analytics on resolved tickets
-- Query: SELECT * FROM support_tickets WHERE status = 'resolved' AND resolved_at IS NOT NULL
CREATE INDEX IF NOT EXISTS idx_tickets_resolved
ON support_tickets(company_id, resolved_at DESC)
WHERE status = 'resolved' AND resolved_at IS NOT NULL;

-- Index 12: AI tier usage index
-- Purpose: Analytics on AI tier usage patterns
-- Query: SELECT * FROM support_tickets WHERE ai_tier_used = 'heavy'
CREATE INDEX IF NOT EXISTS idx_tickets_ai_tier
ON support_tickets(company_id, ai_tier_used);

-- ─────────────────────────────────────────────────────────────────────────────
-- Index Statistics and Monitoring
-- ─────────────────────────────────────────────────────────────────────────────

-- Analyze table after index creation for query planner optimization
ANALYZE support_tickets;

-- Comment on indexes for documentation
COMMENT ON INDEX idx_tickets_company_id IS 'Primary tenant isolation - filters tickets by company';
COMMENT ON INDEX idx_tickets_status IS 'Status filtering - open/pending_approval/resolved/escalated';
COMMENT ON INDEX idx_tickets_created_at IS 'Time-based sorting - newest first';
COMMENT ON INDEX idx_tickets_company_status_created IS 'Composite: most common query pattern';
COMMENT ON INDEX idx_tickets_priority IS 'Priority queue management by AI confidence';
COMMENT ON INDEX idx_tickets_channel IS 'Channel filtering - chat/email/sms/voice';
COMMENT ON INDEX idx_tickets_customer_email IS 'Customer ticket history lookup';
COMMENT ON INDEX idx_tickets_category IS 'Category-based filtering';
COMMENT ON INDEX idx_tickets_assigned IS 'Agent assignment lookup (partial)';
COMMENT ON INDEX idx_tickets_pending_approval IS 'Approval queue (partial, critical)';
COMMENT ON INDEX idx_tickets_resolved IS 'Resolved ticket analytics (partial)';
COMMENT ON INDEX idx_tickets_ai_tier IS 'AI tier usage analytics';
