"""Tenant-isolated, encrypted Superglue call recovery queue.

Revision ID: 048_superglue_call_queue_security
Revises: 047_ticket_tool_execution_idempotency
"""
from alembic import op
import sqlalchemy as sa

revision = "048_superglue_call_queue_security"
down_revision = "047_ticket_tool_execution_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("superglue_call_queue"):
        op.create_table(
            "superglue_call_queue",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "company_id",
                sa.String(length=36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("tool_id", sa.String(length=255), nullable=False),
            sa.Column("input_data", sa.Text(), nullable=False),
            sa.Column("ticket_id", sa.String(length=128), nullable=True),
            sa.Column("agent_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("max_retries", sa.Integer(), nullable=True, server_default="2"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("result_data", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
    else:
        columns = {column["name"]: column for column in inspector.get_columns("superglue_call_queue")}
        if "company_id" not in columns:
            op.add_column(
                "superglue_call_queue",
                sa.Column("company_id", sa.String(length=36), nullable=True),
            )
        if bind.dialect.name == "postgresql":
            if "tool_id" in columns:
                op.alter_column(
                    "superglue_call_queue",
                    "tool_id",
                    existing_type=sa.String(length=100),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                )
            if "ticket_id" in columns:
                op.alter_column(
                    "superglue_call_queue",
                    "ticket_id",
                    existing_type=sa.String(length=36),
                    type_=sa.String(length=128),
                    existing_nullable=True,
                )

    if bind.dialect.name == "postgresql":
        foreign_keys = sa.inspect(bind).get_foreign_keys("superglue_call_queue")
        if not any(
            fk.get("constrained_columns") == ["company_id"]
            and fk.get("referred_table") == "companies"
            for fk in foreign_keys
        ):
            op.create_foreign_key(
                "fk_superglue_call_queue_company_id_companies",
                "superglue_call_queue",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="CASCADE",
            )

    indexes = {
        index.get("name") for index in sa.inspect(bind).get_indexes("superglue_call_queue")
    }
    for name, column in (
        ("ix_superglue_call_queue_company_id", "company_id"),
        ("ix_superglue_call_queue_ticket_id", "ticket_id"),
        ("ix_superglue_call_queue_status", "status"),
    ):
        if name not in indexes:
            op.create_index(name, "superglue_call_queue", [column])

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE superglue_call_queue ENABLE ROW LEVEL SECURITY")
        for suffix, command in (
            ("select", "FOR SELECT USING (company_id = app.current_tenant_id())"),
            ("insert", "FOR INSERT WITH CHECK (company_id = app.current_tenant_id())"),
            ("update", "FOR UPDATE USING (company_id = app.current_tenant_id()) "
                       "WITH CHECK (company_id = app.current_tenant_id())"),
            ("delete", "FOR DELETE USING (company_id = app.current_tenant_id())"),
        ):
            op.execute(
                f"DROP POLICY IF EXISTS superglue_call_queue_tenant_{suffix} "
                "ON superglue_call_queue"
            )
            op.execute(
                f"CREATE POLICY superglue_call_queue_tenant_{suffix} "
                f"ON superglue_call_queue {command}"
            )


def downgrade() -> None:
    # Retain queued customer work and its encrypted payloads during rollback.
    if op.get_bind().dialect.name == "postgresql":
        for suffix in ("select", "insert", "update", "delete"):
            op.execute(
                f"DROP POLICY IF EXISTS superglue_call_queue_tenant_{suffix} "
                "ON superglue_call_queue"
            )
        op.execute("ALTER TABLE superglue_call_queue DISABLE ROW LEVEL SECURITY")
