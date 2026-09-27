"""Add trial tracking columns to companies

Revision ID: 032_company_trial_fields
Revises: 031_agent_capabilities
Create Date: 2026-07-13

Adds four columns to the `companies` table to support the free-trial system
(24 hours OR 15 tickets, whichever hits first, no card on file).

  - is_trial:              bool, default True. Flipped to False on first
                           paid subscription activation.
  - trial_started_at:      DateTime, set at signup. NULL when not in trial.
  - trial_ends_at:         DateTime, set at signup = trial_started_at + 24h.
                           NULL when not in trial or after trial ends.
  - trial_tickets_used:    int, default 0. Incremented on every ticket
                           created while is_trial is True. Preserved
                           after trial ends (for analytics).

Existing companies (already signed up before this migration) get
is_trial=False so they are NOT accidentally locked out as trial users.
Their trial_* fields stay NULL.
"""
from alembic import op
import sqlalchemy as sa


revision = "032_company_trial_fields"
down_revision = "031_agent_capabilities"
branch_labels = None
depends_on = None


def upgrade():
    # Add columns with server defaults so existing rows get populated
    # automatically. No need for a separate UPDATE statement.
    op.add_column(
        "companies",
        sa.Column(
            "is_trial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "companies",
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column(
            "trial_tickets_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade():
    op.drop_column("companies", "trial_tickets_used")
    op.drop_column("companies", "trial_ends_at")
    op.drop_column("companies", "trial_started_at")
    op.drop_column("companies", "is_trial")
