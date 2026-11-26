"""Add tenant row-level security to Paddle tables created after migration 022.

Migration 022's tenant table list includes these tables, but migration 023
creates them only after 022 has already run. Migration 042 enables RLS and
adds service-role access; this migration adds the missing tenant policies.
"""
from alembic import op
import sqlalchemy as sa

revision = "049_paddle_tenant_rls"
down_revision = "048_superglue_call_queue_security"
branch_labels = None
depends_on = None

TABLES = ("paddle_webhook_events", "paddle_reconciliation_reports")
POLICIES = (
    ("select", "FOR SELECT USING (company_id = app.current_tenant_id())"),
    ("insert", "FOR INSERT WITH CHECK (company_id = app.current_tenant_id())"),
    ("update", "FOR UPDATE USING (company_id = app.current_tenant_id())"),
    ("delete", "FOR DELETE USING (company_id = app.current_tenant_id())"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    for table in TABLES:
        if not inspector.has_table(table):
            raise RuntimeError(f"Expected {table} table before applying tenant RLS")
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "company_id" not in columns:
            raise RuntimeError(f"Expected {table}.company_id before applying tenant RLS")

        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        for suffix, clause in POLICIES:
            policy_name = f"{table}_tenant_{suffix}"
            op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
            op.execute(f"CREATE POLICY {policy_name} ON {table} {clause}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Keep RLS enabled and the service-role policy from migration 042 intact.
    for table in TABLES:
        for suffix, _ in POLICIES:
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_{suffix} ON {table}")
