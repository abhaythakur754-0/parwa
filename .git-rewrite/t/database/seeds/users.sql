-- database/seeds/users.sql
-- Seed script to insert admin users for each of the test tenants.
-- Depends on clients.sql being executed first (for foreign key constraints).

-- Using bcrypted password hash for 'password123'
-- ($2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO)

INSERT INTO users (id, tenant_id, email, password_hash, role, is_active)
VALUES
  (
    '10000000-0000-0000-0000-000000000001', 
    '11111111-1111-1111-1111-111111111111', 
    'admin@acmemini.com', 
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO', 
    'admin', 
    true
  ),
  (
    '20000000-0000-0000-0000-000000000002', 
    '22222222-2222-2222-2222-222222222222', 
    'admin@globexstandard.com', 
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO', 
    'admin', 
    true
  ),
  (
    '30000000-0000-0000-0000-000000000003', 
    '33333333-3333-3333-3333-333333333333', 
    'admin@initechenterprise.com', 
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INfO', 
    'admin', 
    true
  )
ON CONFLICT (email) DO NOTHING;
