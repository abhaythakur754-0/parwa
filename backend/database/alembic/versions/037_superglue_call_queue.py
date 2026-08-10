"""Create superglue_call_queue table — DB-backed queue for Superglue execute_tool calls

Revision ID: 037_superglue_call_queue
Revises: 036_llm_request_queue
Create Date: 2026-08-10

User vision: 'free render can erase the ram thats why i am saying there
and other data also'

Same DB-backed pattern as llm_request_queue. When PARWA calls
execute_tool() on Superglue, the call gets persisted to DB before the
HTTP request. On success → delete. On Render restart → recovery worker
retries the call.

This prevents lost refunds/cancellations when Render restarts mid-call.
"""
from alembic import op
import sqlalchemy as sa


revision = "037_superglue_call_queue"
down_revision = "036_llm_request_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "superglue_call_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=True, index=True),
        sa.Column("tool_id", sa.String(100), nullable=False),
        sa.Column("input_data", sa.Text, nullable=False),  # JSON of inputs
        sa.Column("ticket_id", sa.String(36), nullable=True, index=True),
        sa.Column("agent_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        # pending: queued
        # in_progress: HTTP call in flight
        # completed: success (will be deleted)
        # failed: max retries exceeded (kept for audit)
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("max_retries", sa.Integer, default=2),  # fewer than LLM — HTTP is fast
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("result_data", sa.Text, nullable=True),  # cached result for recovery
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_superglue_call_queue_status",
        "superglue_call_queue",
        ["status"],
    )


def downgrade():
    op.drop_index("ix_superglue_call_queue_status", table_name="superglue_call_queue")
    op.drop_table("superglue_call_queue")
