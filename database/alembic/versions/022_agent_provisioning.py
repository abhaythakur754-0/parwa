"""022_agent_provisioning: pending_agents table

F-099: Add/Scale Agent (Paddle Trigger)
Revises: 020_custom_integrations
"""

from alembic import op
import sqlalchemy as sa

revision = "022_agent_provisioning"
down_revision = "020_custom_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("agent_name", sa.String(200), nullable=False),
        sa.Column("specialty", sa.String(50), nullable=False),
        sa.Column("channels", sa.Text, nullable=False, server_default="[]"),
        sa.Column("paddle_checkout_id", sa.String(255), nullable=True),
        sa.Column("paddle_transaction_id", sa.String(255), nullable=True),
        sa.Column("paddle_event_id", sa.String(255), nullable=True, unique=True),
        sa.Column(
            "payment_status", sa.String(20), nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "provisioning_status", sa.String(20), nullable=False,
            server_default="awaiting_payment",
        ),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("provisioned_at", sa.DateTime),
        sa.Column("expires_at", sa.DateTime),
        sa.CheckConstraint(
            "payment_status IN ('pending','paid','failed','refunded','expired')",
            name="ck_pending_agent_payment_status",
        ),
        sa.CheckConstraint(
            "provisioning_status IN ('awaiting_payment','provisioning','training','active','failed')",
            name="ck_pending_agent_provisioning_status",
        ),
    )
    # Composite indexes for common query patterns
    op.create_index(
        "ix_pending_agents_company_payment",
        "pending_agents",
        ["company_id", "payment_status"],
    )
    op.create_index(
        "ix_pending_agents_company_provisioning",
        "pending_agents",
        ["company_id", "provisioning_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_pending_agents_company_provisioning", table_name="pending_agents")
    op.drop_index("ix_pending_agents_company_payment", table_name="pending_agents")
    op.drop_table("pending_agents")
