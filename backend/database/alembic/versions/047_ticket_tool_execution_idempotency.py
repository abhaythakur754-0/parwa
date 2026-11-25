"""Atomic tenant-scoped idempotency for agent tool side effects.

Revision ID: 047_ticket_tool_execution_idempotency
Revises: 046_superglue_tenant_accounts
"""
from alembic import op
import sqlalchemy as sa

revision = "047_ticket_tool_execution_idempotency"
down_revision = "046_superglue_tenant_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("ticket_tool_executions"):
        op.create_table(
            "ticket_tool_executions",
            sa.Column("idempotency_key", sa.String(length=512), primary_key=True, nullable=False),
            sa.Column(
                "company_id",
                sa.String(length=36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("ticket_id", sa.String(length=128), nullable=False),
            sa.Column("tool_id", sa.String(length=255), nullable=False),
            sa.Column("action", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("executed_at", sa.DateTime(), nullable=True),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("ticket_tool_executions")}
        if "company_id" not in columns:
            op.add_column(
                "ticket_tool_executions",
                sa.Column("company_id", sa.String(length=36), nullable=True),
            )
        if "status" not in columns:
            op.add_column(
                "ticket_tool_executions",
                sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
            )
        if "error_message" not in columns:
            op.add_column(
                "ticket_tool_executions",
                sa.Column("error_message", sa.Text(), nullable=True),
            )
        if "created_at" not in columns:
            op.add_column(
                "ticket_tool_executions",
                sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
            )
        if bind.dialect.name == "postgresql":
            op.alter_column(
                "ticket_tool_executions",
                "idempotency_key",
                existing_type=sa.String(length=200),
                type_=sa.String(length=512),
                existing_nullable=False,
            )
            op.alter_column(
                "ticket_tool_executions",
                "ticket_id",
                existing_type=sa.String(length=36),
                type_=sa.String(length=128),
                existing_nullable=False,
            )
            op.alter_column(
                "ticket_tool_executions",
                "tool_id",
                existing_type=sa.String(length=200),
                type_=sa.String(length=255),
                existing_nullable=False,
            )
            op.alter_column(
                "ticket_tool_executions",
                "executed_at",
                existing_type=sa.DateTime(),
                nullable=True,
            )

    if bind.dialect.name == "postgresql":
        refreshed = sa.inspect(bind)
        foreign_keys = refreshed.get_foreign_keys("ticket_tool_executions")
        if not any(
            fk.get("constrained_columns") == ["company_id"]
            and fk.get("referred_table") == "companies"
            for fk in foreign_keys
        ):
            op.create_foreign_key(
                "fk_ticket_tool_executions_company_id_companies",
                "ticket_tool_executions",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="CASCADE",
            )

        # Backfill tenant ownership from the namespaced tool ID where possible.
        op.execute(
            """
            UPDATE ticket_tool_executions
            SET company_id = substring(tool_id from '^tenant_([^_]+)__')
            WHERE company_id IS NULL
              AND tool_id LIKE 'tenant_%__%'
            """
        )
        existing_indexes = {
            index.get("name") for index in sa.inspect(bind).get_indexes("ticket_tool_executions")
        }
        if "ix_ticket_tool_executions_company_id" not in existing_indexes:
            op.create_index(
                "ix_ticket_tool_executions_company_id",
                "ticket_tool_executions",
                ["company_id"],
            )
        if "ix_ticket_tool_executions_ticket_id" not in existing_indexes:
            op.create_index(
                "ix_ticket_tool_executions_ticket_id",
                "ticket_tool_executions",
                ["ticket_id"],
            )
        op.execute("ALTER TABLE ticket_tool_executions ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY ticket_tool_executions_tenant_select
            ON ticket_tool_executions
            FOR SELECT USING (company_id = app.current_tenant_id())
            """
        )
        op.execute(
            """
            CREATE POLICY ticket_tool_executions_tenant_insert
            ON ticket_tool_executions
            FOR INSERT WITH CHECK (company_id = app.current_tenant_id())
            """
        )
        op.execute(
            """
            CREATE POLICY ticket_tool_executions_tenant_update
            ON ticket_tool_executions
            FOR UPDATE
            USING (company_id = app.current_tenant_id())
            WITH CHECK (company_id = app.current_tenant_id())
            """
        )
        op.execute(
            """
            CREATE POLICY ticket_tool_executions_tenant_delete
            ON ticket_tool_executions
            FOR DELETE USING (company_id = app.current_tenant_id())
            """
        )
    else:
        op.create_index(
            "ix_ticket_tool_executions_company_id",
            "ticket_tool_executions",
            ["company_id"],
        )
        op.create_index(
            "ix_ticket_tool_executions_ticket_id",
            "ticket_tool_executions",
            ["ticket_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for suffix in ("select", "insert", "update", "delete"):
            op.execute(
                f"DROP POLICY IF EXISTS ticket_tool_executions_tenant_{suffix} "
                "ON ticket_tool_executions"
            )
        op.execute("ALTER TABLE ticket_tool_executions DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_ticket_tool_executions_company_id", table_name="ticket_tool_executions")
    op.drop_index("ix_ticket_tool_executions_ticket_id", table_name="ticket_tool_executions")
    op.drop_table("ticket_tool_executions")
