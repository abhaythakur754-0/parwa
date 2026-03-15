-- database/seeds/clients.sql
-- Seed script to insert test tenants (one of each plan type: mini, standard, high)

-- We use hardcoded UUIDs so that subsequent seed scripts (users.sql, sample_tickets.sql) 
-- can reliably reference them without relying on subqueries or returning clauses.

INSERT INTO tenants (id, name, plan, is_active)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'Acme Mini Corp', 'mini_parwa', true),
  ('22222222-2222-2222-2222-222222222222', 'Globex Standard LLC', 'parwa', true),
  ('33333333-3333-3333-3333-333333333333', 'Initech Enterprise', 'parwa_high', true)
ON CONFLICT (id) DO NOTHING;
