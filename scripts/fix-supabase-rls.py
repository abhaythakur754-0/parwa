#!/usr/bin/env python3
"""
Enable Row Level Security (RLS) on all public tables in Supabase.

This fixes the Supabase Database Linter warnings:
  - rls_disabled_in_public  (156 warnings)
  - sensitive_columns_exposed (29 warnings)

Strategy:
  1. Enable RLS on every table in the `public` schema.
  2. Add a permissive policy for the `service_role` (the backend connects
     via the service-role Postgres connection string, which bypasses RLS
     anyway, but an explicit policy is good practice and silences the linter).
  3. The `anon` and `authenticated` Postgres roles get NO policies, so
     direct browser access via the Supabase REST API is fully blocked.
     All app traffic must go through the FastAPI backend (which enforces
     JWT + tenant middleware itself).

Safety:
  - The backend uses a direct Postgres connection (postgres superuser),
    which BYPASSES RLS entirely. Enabling RLS will NOT break the app.
  - Idempotent: safe to re-run; uses IF NOT EXISTS / OR REPLACE semantics.
"""

import os
import re
import sys
from pathlib import Path

# --- Parse DATABASE_URL from backend/.env manually (password has '@') ---
BACKEND_ENV = Path("/home/z/my-project/download/parwa/backend/.env")
if not BACKEND_ENV.exists():
    print("ERROR: backend/.env not found", file=sys.stderr)
    sys.exit(1)

raw_url = None
for line in BACKEND_ENV.read_text().splitlines():
    line = line.strip()
    if line.startswith("DATABASE_URL="):
        raw_url = line[len("DATABASE_URL="):].strip().strip('"').strip("'")
        break

if not raw_url or not raw_url.startswith("postgresql://"):
    print(f"ERROR: DATABASE_URL not found or invalid in {BACKEND_ENV}", file=sys.stderr)
    sys.exit(1)

# postgresql://USER:PASSWORD@HOST:PORT/DBNAME
# Password may contain '@', so split from the RIGHT.
m = re.match(r"^postgresql://([^:]+):(.+)@([^:]+):(\d+)/(.+)$", raw_url)
if not m:
    print(f"ERROR: could not parse DATABASE_URL", file=sys.stderr)
    sys.exit(1)

DB_USER = m.group(1)
DB_PASS = m.group(2)
DB_HOST = m.group(3)
DB_PORT = int(m.group(4))
DB_NAME = m.group(5)

print(f"Connecting to: {DB_USER} @ {DB_HOST}:{DB_PORT}/{DB_NAME}")

import psycopg2

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASS,
    dbname=DB_NAME,
    connect_timeout=20,
)
conn.autocommit = False
cur = conn.cursor()

# --- 1. List all base tables in public schema ---
cur.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename
""")
all_tables = [r[0] for r in cur.fetchall()]
print(f"\nFound {len(all_tables)} tables in public schema")

# --- 2. Check current RLS state ---
cur.execute("""
    SELECT count(*)
    FROM pg_tables t
    JOIN pg_class c ON c.relname = t.tablename
    WHERE t.schemaname = 'public' AND c.relrowsecurity = true
""")
rls_before = cur.fetchone()[0]
print(f"Tables with RLS currently ENABLED: {rls_before}")
print(f"Tables with RLS currently DISABLED: {len(all_tables) - rls_before}")

# --- 3. Enable RLS on every table + add permissive service_role policy ---
print("\nEnabling RLS and adding service_role policies...")
enabled = 0
policies_added = 0
errors = []

for tbl in all_tables:
    # Validate table name (defensive — only allow identifiers)
    if not re.match(r"^[a-z_][a-z0-9_]*$", tbl):
        errors.append(f"skip (bad name): {tbl}")
        continue

    try:
        # Enable RLS
        cur.execute(f'ALTER TABLE public."{tbl}" ENABLE ROW LEVEL SECURITY;')
        enabled += 1

        # Force RLS even for table owner (extra safety — table owner normally
        # bypasses RLS unless FORCE is set). The backend connects as the
        # postgres superuser which ALWAYS bypasses RLS, so FORCE only affects
        # non-superuser owners.
        cur.execute(f'ALTER TABLE public."{tbl}" FORCE ROW LEVEL SECURITY;')

        # Drop existing service_role policy if present (idempotent)
        cur.execute(f"""
            DROP POLICY IF EXISTS "service_role_all_{tbl}"
            ON public."{tbl}";
        """)

        # Add permissive policy for service_role (full access)
        cur.execute(f"""
            CREATE POLICY "service_role_all_{tbl}"
            ON public."{tbl}"
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
        """)
        policies_added += 1

    except Exception as e:
        conn.rollback()
        errors.append(f"{tbl}: {e}")
        # Continue with next table
        continue

conn.commit()
print(f"  RLS enabled on {enabled} tables")
print(f"  service_role policies added: {policies_added}")
if errors:
    print(f"\n  {len(errors)} ERRORS:")
    for e in errors[:20]:
        print(f"    - {e}")

# --- 4. Verify final state ---
cur.execute("""
    SELECT count(*)
    FROM pg_tables t
    JOIN pg_class c ON c.relname = t.tablename
    WHERE t.schemaname = 'public' AND c.relrowsecurity = true
""")
rls_after = cur.fetchone()[0]

cur.execute("""
    SELECT count(DISTINCT tablename)
    FROM pg_policies
    WHERE schemaname = 'public'
""")
policies_total = cur.fetchone()[0]

cur.execute("""
    SELECT count(*)
    FROM pg_policies
    WHERE schemaname = 'public' AND policyname LIKE 'service_role_all_%'
""")
service_policies = cur.fetchone()[0]

print("\n" + "=" * 60)
print("FINAL STATE")
print("=" * 60)
print(f"Total public tables:           {len(all_tables)}")
print(f"Tables with RLS enabled:       {rls_after}")
print(f"Tables with RLS disabled:      {len(all_tables) - rls_after}")
print(f"service_role_all_* policies:   {service_policies}")
print(f"Total policies on public:      {policies_total}")

# Show any tables still without RLS
cur.execute("""
    SELECT t.tablename
    FROM pg_tables t
    LEFT JOIN pg_class c ON c.relname = t.tablename
    WHERE t.schemaname = 'public' AND (c.relrowsecurity IS NULL OR c.relrowsecurity = false)
    ORDER BY t.tablename
""")
remaining = [r[0] for r in cur.fetchall()]
if remaining:
    print(f"\nWARNING: {len(remaining)} tables STILL without RLS:")
    for t in remaining:
        print(f"  - {t}")
else:
    print("\n✅ ALL public tables now have RLS enabled")

cur.close()
conn.close()
print("\nDone.")
