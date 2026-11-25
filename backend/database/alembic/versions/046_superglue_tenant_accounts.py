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
    op.create_index(
        "ix_superglue_tenant_accounts_company_id",
        "superglue_tenant_accounts",
        ["company_id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE superglue_tenant_accounts ENABLE ROW LEVEL SECURITY"
        )
        op.execute(
            """
            CREATE POLICY superglue_tenant_accounts_tenant_select
            ON superglue_tenant_accounts
            FOR SELECT USING (company_id = app.current_tenant_id())
            """
        )
        op.execute(
            """
            CREATE POLICY superglue_tenant_accounts_tenant_insert
            ON superglue_tenant_accounts
            FOR INSERT WITH CHECK (company_id = app.current_tenant_id())
            """
        )
        op.execute(
            """
            CREATE POLICY superglue_tenant_accounts_tenant_update
            ON superglue_tenant_accounts
            FOR UPDATE
            USING (company_id = app.current_tenant_id())
            WITH CHECK (company_id = app.current_tenant_id())
            """
        )
        op.execute(
            """
            CREATE POLICY superglue_tenant_accounts_tenant_delete
            ON superglue_tenant_accounts
            FOR DELETE USING (company_id = app.current_tenant_id())
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for suffix in ("select", "insert", "update", "delete"):
            op.execute(
                f"DROP POLICY IF EXISTS superglue_tenant_accounts_tenant_{suffix} "
                "ON superglue_tenant_accounts"
            )
        op.execute(
            "ALTER TABLE superglue_tenant_accounts DISABLE ROW LEVEL SECURITY"
        )
    op.drop_index(
        "ix_superglue_tenant_accounts_company_id",
        table_name="superglue_tenant_accounts",
    )
    op.drop_table("superglue_tenant_accounts")
