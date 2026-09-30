"""Create llm_request_queue table — DB-backed LLM call queue (survives Render restarts)

Revision ID: 036_llm_request_queue
Revises: 035_approval_gates
Create Date: 2026-08-10

User vision: 'see u can keep that request or that queue in database ok well
dont keep that in ram ad here as that request get solved delete that ok
because here free render can erase the ram thats why i am saying there'

Problem: Render free tier restarts wipe RAM. If an LLM call is in the middle
of a 60-second rate-limit wait (asyncio.sleep), the call is LOST on restart.

Solution: Persist every LLM call to DB before making it. On success, delete.
On 429 rate limit, update retry_at timestamp. On Render restart, recovery
worker scans for stuck requests and retries them.

This is the same DB-backed queue pattern used for tickets (pipeline_dispatcher.py).
"""
from alembic import op
import sqlalchemy as sa


revision = "036_llm_request_queue"
down_revision = "035_approval_gates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "llm_request_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=True, index=True),
        sa.Column("provider", sa.String(50), nullable=False),  # nvidia, groq, cerebras
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("messages", sa.Text, nullable=False),  # JSON array of messages
        sa.Column("temperature", sa.Float, default=0.1),
        sa.Column("max_tokens", sa.Integer, default=1000),
        sa.Column("call_id", sa.Integer, nullable=True),
        sa.Column("ticket_id", sa.String(36), nullable=True, index=True),  # for tracing
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        # pending: just queued, not yet called
        # in_progress: worker is calling NVIDIA
        # rate_limited: 429 received, waiting for next_retry_at
        # completed: success (will be deleted)
        # failed: max retries exceeded
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("max_retries", sa.Integer, default=3),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_llm_request_queue_status_retry",
        "llm_request_queue",
        ["status", "next_retry_at"],
    )


def downgrade():
    op.drop_index("ix_llm_request_queue_status_retry", table_name="llm_request_queue")
    op.drop_table("llm_request_queue")
