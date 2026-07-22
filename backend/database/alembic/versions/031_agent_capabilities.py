"""Add domain + capabilities columns to ai_agent_assignments

Revision ID: 031_agent_capabilities
Revises: 030_company_unique_id
Create Date: 2026-07-04

Adds two columns to ai_agent_assignments so user-created agents can declare
what they can handle. Node 1 (classifier) reads these to route tickets to
the right agent, or escalate to human when no agent claims a capability.

  - domain:        free-form string label (e.g. "Refunds", "Legal Review")
  - capabilities:  JSON array of capability keys from the fixed vocabulary:
                   refund_processing, billing_inquiry, technical_support,
                   faq_general, complaint_handling, account_management,
                   fraud_security, shipping_delivery, product_information,
                   legal_review, vip_enterprise, other

Both columns are nullable for backwards compatibility with existing rows.
"""
from alembic import op
import sqlalchemy as sa

revision = "031_agent_capabilities"
down_revision = "030_company_unique_id"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_agent_assignments",
        sa.Column("domain", sa.String(100), nullable=True),
    )
    op.add_column(
        "ai_agent_assignments",
        sa.Column("capabilities", sa.Text, nullable=True, server_default="[]"),
    )
    op.create_index(
        "ix_ai_agent_assignments_domain",
        "ai_agent_assignments",
        ["domain"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_ai_agent_assignments_domain", table_name="ai_agent_assignments",
    )
    op.drop_column("ai_agent_assignments", "capabilities")
    op.drop_column("ai_agent_assignments", "domain")
