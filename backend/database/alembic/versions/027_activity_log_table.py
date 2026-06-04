"""Create activity_log table for Jarvis non-agentic awareness

Revision ID: 027
Revises: 026
Create Date: 2026-05-19

This table stores EVERY action in the system that is NOT handled by
variant agents. Jarvis reads this for awareness of non-agentic parts.
For agentic parts, Jarvis asks variant agents directly via variant_bridge.
"""

from alembic import op
import sqlalchemy as sa


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        # Who
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        # What
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        # What was affected
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        # Context
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("route", sa.String(500), nullable=True),
        sa.Column("method", sa.String(10), nullable=True),
        # Details
        sa.Column("details_json", sa.Text, server_default="{}"),
        # Importance
        sa.Column("importance", sa.String(10), nullable=False, server_default="info"),
        # Timestamps
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        # Pruning
        sa.Column("expires_at", sa.DateTime, nullable=True),
        # Check constraints
        sa.CheckConstraint(
            "actor_type IN ('user','system','agent','jarvis','cron','webhook','api')",
            name="ck_activity_actor_type",
        ),
        sa.CheckConstraint(
            "category IN ('user_action','billing','system','channel','workflow',"
            "'configuration','security','integration','notification','training')",
            name="ck_activity_category",
        ),
        sa.CheckConstraint(
            "importance IN ('info','low','medium','high','critical')",
            name="ck_activity_importance",
        ),
    )

    # Indexes for fast querying
    op.create_index("ix_activity_comp_created", "activity_log", ["company_id", "created_at"])
    op.create_index("ix_activity_comp_category", "activity_log", ["company_id", "category"])
    op.create_index("ix_activity_comp_entity", "activity_log", ["company_id", "entity_type", "entity_id"])
    op.create_index("ix_activity_comp_importance", "activity_log", ["company_id", "importance"])
    op.create_index("ix_activity_comp_occurred", "activity_log", ["company_id", "occurred_at"])
    op.create_index("ix_activity_session", "activity_log", ["session_id"])
    op.create_index("ix_activity_actor", "activity_log", ["company_id", "actor_type", "actor_id"])


def downgrade() -> None:
    op.drop_index("ix_activity_actor", table_name="activity_log")
    op.drop_index("ix_activity_session", table_name="activity_log")
    op.drop_index("ix_activity_comp_occurred", table_name="activity_log")
    op.drop_index("ix_activity_comp_importance", table_name="activity_log")
    op.drop_index("ix_activity_comp_entity", table_name="activity_log")
    op.drop_index("ix_activity_comp_category", table_name="activity_log")
    op.drop_index("ix_activity_comp_created", table_name="activity_log")
    op.drop_table("activity_log")
