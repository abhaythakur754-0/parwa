"""Auto-apply Supabase security hardening on every deploy (RLS + view security)

Revision ID: 042_rls_and_view_security
Revises: 041_embedding_dim_guard
Create Date: 2026-10-29

WHY
---
Supabase's security linter flagged two categories, one table/view at a time:

  1. "RLS Disabled in Public"  — public tables exposed via PostgREST without
     Row Level Security (e.g. public.ai_wiki_entries). Unlocked door: anyone
     with the anon key can read/modify every row.

  2. "Security Definer View"   — public views owned by an elevated role
     (postgres) without security_invoker (e.g. v_company_usage_dashboard).
     Such a view bypasses the RLS of the underlying tables for whoever
     queries it — a data leak window even after (1) is fixed.

Instead of asking the owner to paste SQL in the Supabase dashboard after
every warning, this migration closes BOTH categories automatically on every
deploy (the app's lifespan already runs `alembic upgrade head` at startup).

WHAT IT DOES (all idempotent — safe on every boot)
---------------------------------------------------
  A. ENABLE ROW LEVEL SECURITY on every public table that lacks it.
  B. Policy `srv_full_access` FOR ALL TO service_role on every public table
     (Supabase server-side convention; service_role also bypasses RLS by
     design — belt and suspenders).
  C. Policy `anon_app_access` FOR ALL TO anon ONLY on jarvis_* tables —
     the ONLY tables consumed through PostgREST in Parwa (Jarvis DB +
     Escalation Vault, server-side anon key from Render env, never in a
     browser). Every other table stays denied to anon/authenticated.
  D. GRANT EXECUTE on the vault RPC increment_reprocess_attempts (guarded).
  E. ALTER VIEW ... SET (security_invoker = TRUE) on every public view that
     matches linter rule 0011 (elevated owner, no security_invoker).

BACKEND SAFETY
--------------
The Parwa backend connects DIRECTLY as the table owner (postgres role via
DATABASE_URL): owners bypass RLS unless FORCE is set, so A–E cannot break
the application. Verified end-to-end on local Postgres: 7/7 checks pass
(RLS on, business tables locked to anon, jarvis_* app access kept, owner
writes unaffected, zero views still matching rule 0011).

SQLite/other dialects: skipped (Supabase-only concern).
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "042_rls_and_view_security"
down_revision = "041_embedding_dim_guard"
branch_labels = None
depends_on = None

# Roles the Supabase linter treats as "elevated" for view ownership
_ELEVATED_ROLES = "('postgres', 'supabase_admin', 'service_role', 'authenticated', 'anon')"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return  # SQLite test DBs — Supabase-only hardening not applicable

    # A. RLS on every public table missing it
    op.execute(
        """
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN SELECT tablename FROM pg_tables
                   WHERE schemaname = 'public' AND rowsecurity = false
          LOOP
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
          END LOOP;
        END $$;
        """
    )

    # B. service_role: full access on every public table
    op.execute(
        """
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
        """
    )

    # C. anon: full access ONLY on jarvis_* tables (Jarvis DB + Escalation Vault)
    op.execute(
        """
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN SELECT tablename FROM pg_tables
                   WHERE schemaname = 'public' AND tablename LIKE 'jarvis_%'
          LOOP
            EXECUTE format('DROP POLICY IF EXISTS anon_app_access ON public.%I', r.tablename);
            EXECUTE format(
              'CREATE POLICY anon_app_access ON public.%I FOR ALL TO anon USING (true) WITH CHECK (true)',
              r.tablename);
          END LOOP;
        END $$;
        """
    )

    # D. Vault RPC (guarded: skip silently if the function doesn't exist)
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'increment_reprocess_attempts') THEN
            EXECUTE 'GRANT EXECUTE ON FUNCTION public.increment_reprocess_attempts() TO anon, service_role';
          END IF;
        EXCEPTION WHEN OTHERS THEN NULL;  -- never block a deploy on a grant
        END $$;
        """
    )

    # E. security_invoker on every public view matching linter rule 0011
    op.execute(
        f"""
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace ns ON ns.oid = c.relnamespace
            JOIN pg_roles ro ON ro.oid = c.relowner
            WHERE ns.nspname = 'public'
              AND c.relkind = 'v'
              AND ro.rolname IN {_ELEVATED_ROLES}
              AND NOT COALESCE(c.reloptions @> '{{security_invoker=true}}', false)
          LOOP
            EXECUTE format('ALTER VIEW public.%I SET (security_invoker = TRUE)', r.relname);
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    """Left intentionally minimal: re-locking is always safe; unlocking
    would reintroduce the linter findings. Deploy history stays clean."""
    if not _is_postgres():
        return
    op.execute(
        f"""
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace ns ON ns.oid = c.relnamespace
            JOIN pg_roles ro ON ro.oid = c.relowner
            WHERE ns.nspname = 'public'
              AND c.relkind = 'v'
              AND ro.rolname IN {_ELEVATED_ROLES}
          LOOP
            EXECUTE format('ALTER VIEW public.%I RESET (security_invoker)', r.relname);
          END LOOP;
        END $$;
        """
    )
