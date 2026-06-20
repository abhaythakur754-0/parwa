"""023_paddle_reconciliation: Paddle webhook reconciliation tables

Revision ID: 023
Revises: 022_enable_rls
Create Date: 2026-05-12

Tables for Paddle webhook idempotency and reconciliation:
- paddle_webhook_events: Tracks every Paddle webhook with idempotency
- paddle_reconciliation_reports: Periodic reconciliation audit trail

These tables support:
- Exactly-once processing of Paddle webhooks
- Dead letter queue for failed webhooks
- Automatic reconciliation of payment state
- Full audit trail for all payment events

BC-001: company_id indexed on every table
BC-008: Null-safe columns for graceful degradation
BC-012: All timestamps UTC
"""

from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022_enable_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ════════════════════════════════════════════════════════════════
    # PADDLE WEBHOOK EVENTS
    # ════════════════════════════════════════════════════════════════

    op.create_table(
        "paddle_webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "idempotency_key", sa.String(64),
            unique=True, nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column(
            "status", sa.String(20),
            nullable=False, server_default="pending",
        ),
        sa.Column("processing_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True, index=True,
        ),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at", sa.DateTime,
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime,
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("result_json", sa.Text, nullable=True),
        # CHECK constraints
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','failed','dead_letter')",
            name="ck_paddle_webhook_status",
        ),
    )
    # Indexes for common query patterns
    op.create_index(
        "idx_paddle_webhook_idempotency",
        "paddle_webhook_events",
        ["idempotency_key"],
    )
    op.create_index(
        "idx_paddle_webhook_status",
        "paddle_webhook_events",
        ["status"],
    )
    op.create_index(
        "idx_paddle_webhook_company",
        "paddle_webhook_events",
        ["company_id"],
    )
    op.create_index(
        "idx_paddle_webhook_event_type",
        "paddle_webhook_events",
        ["event_type"],
    )

    # ════════════════════════════════════════════════════════════════
    # PADDLE RECONCILIATION REPORTS
    # ════════════════════════════════════════════════════════════════

    op.create_table(
        "paddle_reconciliation_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "report_type", sa.String(20),
            nullable=False, server_default="periodic",
        ),
        sa.Column("subscriptions_checked", sa.Integer, nullable=False, server_default="0"),
        sa.Column("discrepancies_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("corrections_applied", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "report_json", sa.JSON,
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "created_at", sa.DateTime,
            nullable=False, server_default=sa.func.now(),
        ),
        # CHECK constraints
        sa.CheckConstraint(
            "report_type IN ('periodic','manual','on_demand','startup')",
            name="ck_paddle_recon_report_type",
        ),
    )
    op.create_index(
        "idx_paddle_recon_company",
        "paddle_reconciliation_reports",
        ["company_id"],
    )


def downgrade() -> None:
    # Drop in reverse creation order
    op.drop_table("paddle_reconciliation_reports")
    op.drop_table("paddle_webhook_events")
