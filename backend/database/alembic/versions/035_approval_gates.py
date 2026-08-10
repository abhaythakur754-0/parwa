"""Add approval gate columns to ai_agent_assignments

Revision ID: 035_approval_gates
Revises: 034_superglue_tool_columns
Create Date: 2026-08-10

Eliminates the risky part of tool execution. When a customer requests a
risky action (refund > $1000, cancel subscription, delete account), the
tool execution is PAUSED and the ticket moves to "Pending Approval" queue.

Admin reviews and clicks Approve/Reject. This makes the system safe for
production — no unattended $5000 refunds.

Columns added:
  - approval_required: BOOL, default false
      True = this agent's tool does dangerous actions, needs human approval
  - approval_threshold_cents: INT, default 0
      Above this amount (in cents), approval is required.
      0 = always require approval when approval_required=True

Default thresholds by capability (set by Builder Agent):
  refund_processing → approval_required=True, threshold=100000 ($1000)
  subscription_management → approval_required=True, threshold=0 (always)
  account_management → approval_required=True, threshold=0 (always)
  customer_lookup → approval_required=False (read-only)
  faq_general → approval_required=False (no tool)
"""
from alembic import op
import sqlalchemy as sa


revision = "035_approval_gates"
down_revision = "034_superglue_tool_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_agent_assignments",
        sa.Column("approval_required", sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.add_column(
        "ai_agent_assignments",
        sa.Column("approval_threshold_cents", sa.Integer(), nullable=True, server_default="0"),
    )

    # Backfill existing agents: default approval_required to false
    op.execute(
        "UPDATE ai_agent_assignments SET approval_required = false "
        "WHERE approval_required IS NULL"
    )
    op.execute(
        "UPDATE ai_agent_assignments SET approval_threshold_cents = 0 "
        "WHERE approval_threshold_cents IS NULL"
    )


def downgrade():
    op.drop_column("ai_agent_assignments", "approval_threshold_cents")
    op.drop_column("ai_agent_assignments", "approval_required")
