"""Add Superglue tool linkage columns to ai_agent_assignments

Revision ID: 034_superglue_tool_columns
Revises: 033_enable_pgvector
Create Date: 2026-08-10

Adds 4 columns to ai_agent_assignments so each AI agent can be linked to a
Superglue multi-step tool. When the Builder Agent creates an AI agent config,
it ALSO asks Superglue to generate a multi-step tool for it. The returned
tool_id is stored here.

When a ticket routes to this agent, Node 5 calls execute_tool(superglue_tool_id)
to run the chain directly - 0 LLM calls, ~5-7s per ticket (fast path).

Columns added:
  - superglue_tool_id:          VARCHAR(100), nullable, indexed
  - superglue_tool_status:      VARCHAR(20), default 'none'
      Values: none | pending | active | failed | disabled
  - superglue_tool_definition:  TEXT, nullable (cached JSON for audit)
  - superglue_tool_created_at:   DateTime, nullable

All columns nullable for backwards compatibility - existing agents get
status='none' and continue to work via KB fallback.
"""
from alembic import op
import sqlalchemy as sa


revision = "034_superglue_tool_columns"
down_revision = "033_enable_pgvector"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_agent_assignments",
        sa.Column("superglue_tool_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "ai_agent_assignments",
        sa.Column("superglue_tool_status", sa.String(20), nullable=True, server_default="none"),
    )
    op.add_column(
        "ai_agent_assignments",
        sa.Column("superglue_tool_definition", sa.Text, nullable=True),
    )
    op.add_column(
        "ai_agent_assignments",
        sa.Column("superglue_tool_created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_ai_agent_assignments_superglue_tool_id",
        "ai_agent_assignments",
        ["superglue_tool_id"],
        unique=False,
    )

    op.execute(
        "UPDATE ai_agent_assignments SET superglue_tool_status = 'none' "
        "WHERE superglue_tool_status IS NULL"
    )


def downgrade():
    op.drop_index(
        "ix_ai_agent_assignments_superglue_tool_id",
        table_name="ai_agent_assignments",
    )
    op.drop_column("ai_agent_assignments", "superglue_tool_created_at")
    op.drop_column("ai_agent_assignments", "superglue_tool_definition")
    op.drop_column("ai_agent_assignments", "superglue_tool_status")
    op.drop_column("ai_agent_assignments", "superglue_tool_id")
