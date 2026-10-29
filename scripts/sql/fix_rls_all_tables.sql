-- ============================================================================
-- FIX: Supabase linter warning "RLS Disabled in Public"
-- Flags: public.ai_wiki_entries (and every other public table without RLS)
--
-- WHY THIS MATTERS (simple):
--   Supabase gives every project a public REST "front door" (PostgREST).
--   A table without RLS (Row Level Security) = an unlocked door: anyone with
--   the public anon key could read/modify ALL rows of that table.
--
-- WHY YOUR BACKEND KEEPS WORKING (simple):
--   The Parwa backend connects DIRECTLY to Postgres as the table owner
--   (postgres role via DATABASE_URL). Owners bypass RLS unless FORCE is set.
--   So locking the REST front door does NOT affect the backend.
--
-- WHAT THIS DOES:
--   1. Enables RLS on EVERY public table that is missing it (fixes the
--      linter for all tables at once, not just ai_wiki_entries).
--   2. Adds a full-access policy for the `service_role` on every table
--      (Supabase convention for server-side code; service_role also
--      bypasses RLS by design — belt and suspenders).
--   3. Adds a full-access policy for `anon` ONLY on jarvis_* tables,
--      because Jarvis DB + Escalation Vault call PostgREST with the anon
--      key from your own server (key lives in Render env vars, never in
--      a browser). Every other table stays DENIED to anon/authenticated.
--
-- SAFE TO RE-RUN (idempotent). HOW TO RUN:
--   Supabase Dashboard → SQL Editor → New query → paste → Run.
--   Then re-check Database → Linter (warnings disappear on next scan).
-- ============================================================================

-- 1. Enable RLS on every public table that doesn't have it
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND rowsecurity = false
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
    RAISE NOTICE 'RLS enabled on public.%', r.tablename;
  END LOOP;
END $$;

-- 2. service_role: full access on every public table (server-side convention)
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('DROP POLICY IF EXISTS srv_full_access ON public.%I', r.tablename);
    EXECUTE format(
      'CREATE POLICY srv_full_access ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)',
      r.tablename);
  END LOOP;
END $$;

-- 3. anon: full access ONLY on jarvis_* tables (Jarvis DB + Escalation Vault
--    use the anon key server-side via PostgREST). All other tables: locked.
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename LIKE 'jarvis_%'
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS anon_app_access ON public.%I', r.tablename);
    EXECUTE format(
      'CREATE POLICY anon_app_access ON public.%I FOR ALL TO anon USING (true) WITH CHECK (true)',
      r.tablename);
  END LOOP;
END $$;

-- 4. Vault RPC used by escalation_vault (guarded: skip silently if absent)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'increment_reprocess_attempts') THEN
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.increment_reprocess_attempts() TO anon, service_role';
    RAISE NOTICE 'EXECUTE granted on increment_reprocess_attempts';
  ELSE
    RAISE NOTICE 'increment_reprocess_attempts not found — skipped';
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'RPC grant skipped: %', SQLERRM;
END $$;

-- 5. Report what the linter will now see
SELECT
  (SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity)      AS tables_with_rls,
  (SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity)  AS tables_still_missing_rls;
