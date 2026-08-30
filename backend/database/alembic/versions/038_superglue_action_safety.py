"""Create superglue_action_safety table — persisted safety classification for Superglue tools

Revision ID: 038_superglue_action_safety
Revises: 037_superglue_call_queue
Create Date: 2026-08-10

Caches the safety classification (READ/WRITE/FINANCIAL/DESTRUCTIVE/SENSITIVE_PII)
so PARWA doesn't reclassify on every Superglue tool call.
"""
from alembic import op
import sqlalchemy as sa


revision = "038_superglue_action_safety"
down_revision = "037_superglue_call_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "superglue_action_safety",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("tool_id", sa.String(100), nullable=False),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("safety_level", sa.String(50), nullable=False),
        sa.Column("needs_approval", sa.Boolean, default=False),
        sa.Column("regulatory_frameworks", sa.Text, nullable=True),
        sa.Column("output_schema", sa.Text, nullable=True),
        sa.Column("approval_required_override", sa.Boolean, default=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_superglue_action_safety_company_id", "superglue_action_safety", ["company_id"])
    op.create_index("ix_superglue_action_safety_tool_id", "superglue_action_safety", ["tool_id"])


def downgrade():
    op.drop_index("ix_superglue_action_safety_tool_id", table_name="superglue_action_safety")
    op.drop_index("ix_superglue_action_safety_company_id", table_name="superglue_action_safety")
    op.drop_table("superglue_action_safety")
