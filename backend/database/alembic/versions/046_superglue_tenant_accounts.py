"""Persist encrypted per-tenant Superglue service-account credentials.

Revision ID: 046_superglue_tenant_accounts
Revises: 045_agent_assignment_tenant_scope
"""
from alembic import op
import sqlalchemy as sa

revision = "046_superglue_tenant_accounts"
down_revision = "045_agent_assignment_tenant_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("superglue_tenant_accounts"):
        op.create_table(
            "superglue_tenant_accounts",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "company_id",
                sa.String(length=36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("service_account_id", sa.String(length=255), nullable=False, unique=True),
            sa.Column("api_key_encrypted", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "company_id", name="uq_superglue_tenant_account_company"
            ),
        )

    existing_indexes = {
        index.get("name") for index in sa.inspect(bind).get_indexes("superglue_tenant_accounts")
    }
    if "ix_superglue_tenant_accounts_company_id" not in existing_indexes:
        op.create_index(
            "ix_superglue_tenant_accounts_company_id",
            "superglue_tenant_accounts",
            ["company_id"],
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE superglue_tenant_accounts ENABLE ROW LEVEL SECURITY"
        )
        for suffix, command in (
            ("select", "FOR SELECT USING (company_id = app.current_tenant_id())"),
            ("insert", "FOR INSERT WITH CHECK (company_id = app.current_tenant_id())"),
            ("update", "FOR UPDATE USING (company_id = app.current_tenant_id()) "
                       "WITH CHECK (company_id = app.current_tenant_id())"),
            ("delete", "FOR DELETE USING (company_id = app.current_tenant_id())"),
        ):
            op.execute(
                f"DROP POLICY IF EXISTS superglue_tenant_accounts_tenant_{suffix} "
                "ON superglue_tenant_accounts"
            )
            op.execute(
                f"CREATE POLICY superglue_tenant_accounts_tenant_{suffix} "
                f"ON superglue_tenant_accounts {command}"
            )


def downgrade() -> None:
    # Retain encrypted tenant credentials during rollback. Older application
    # versions ignore this table, and deleting it would force every customer
    # to reconnect all external systems after a rollback.
    if op.get_bind().dialect.name == "postgresql":
        for suffix in ("select", "insert", "update", "delete"):
            op.execute(
                f"DROP POLICY IF EXISTS superglue_tenant_accounts_tenant_{suffix} "
                "ON superglue_tenant_accounts"
            )
        op.execute(
            "ALTER TABLE superglue_tenant_accounts DISABLE ROW LEVEL SECURITY"
        )
