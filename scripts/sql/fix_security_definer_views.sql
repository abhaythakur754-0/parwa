-- ============================================================================
-- FIX: Supabase linter warning "Security Definer View"
-- Flags: public.v_company_usage_dashboard
--
-- WHY THIS MATTERS (simple):
--   In Postgres, a view normally runs with its OWNER's powers. Your public
--   views are owned by the powerful `postgres` role — so through such a
--   view, even the public anon key can see ALL rows, ignoring the RLS door
--   locks on the underlying tables. Supabase's linter calls this the
--   "SECURITY DEFINER property".
--
-- THE FIX (simple):
--   Flip the view(s) to security_invoker = the view then uses the DOOR
--   LOCKS of whoever is asking:
--     * Parwa backend (owner/direct connection) → full access, unchanged
--     * public anon key → 0 rows (usage data can no longer leak)
--   This is exactly Supabase's recommended remediation.
--
-- DETECTION MATCHES THE LINTER 1:1 (rule 0011):
--   views in `public` owned by an elevated role (postgres / supabase_admin /
--   service_role / authenticated / anon) WITHOUT security_invoker=true.
--
-- SAFE TO RE-RUN (idempotent). HOW TO RUN:
--   Supabase Dashboard → SQL Editor → New query → paste → Run.
--   Then re-check Database → Linter.
-- ============================================================================

-- 1. Fix the flagged view directly
ALTER VIEW IF EXISTS public.v_company_usage_dashboard SET (security_invoker = TRUE);

-- 2. Fix EVERY view in public that matches the linter rule
--    (elevated owner + no security_invoker) — closes this whole category
DO $$
DECLARE r RECORD; n int := 0;
BEGIN
  FOR r IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace ns ON ns.oid = c.relnamespace
    JOIN pg_roles ro ON ro.oid = c.relowner
    WHERE ns.nspname = 'public'
      AND c.relkind = 'v'
      AND ro.rolname IN ('postgres', 'supabase_admin', 'service_role', 'authenticated', 'anon')
      AND NOT COALESCE(c.reloptions @> '{security_invoker=true}', false)
  LOOP
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = TRUE)', r.relname);
    n := n + 1;
    RAISE NOTICE 'fixed: public.%', r.relname;
  END LOOP;
  RAISE NOTICE 'total views fixed: %', n;
END $$;

-- 3. Final check: must return ZERO rows (same predicate as the linter)
SELECT c.relname AS view_still_flagged
FROM pg_class c
JOIN pg_namespace ns ON ns.oid = c.relnamespace
JOIN pg_roles ro ON ro.oid = c.relowner
WHERE ns.nspname = 'public'
  AND c.relkind = 'v'
  AND ro.rolname IN ('postgres', 'supabase_admin', 'service_role', 'authenticated', 'anon')
  AND NOT COALESCE(c.reloptions @> '{security_invoker=true}', false);
