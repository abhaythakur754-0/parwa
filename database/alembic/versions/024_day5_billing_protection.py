"""024_day5_billing_protection: Day 5 — Chargeback, Credit Balance, Spending Caps, Dead-Letter Webhooks, Webhook Health, Refund Audit

Creates 6 new tables for billing protection and financial safeguards:
1. chargebacks           — Track chargebacks from payment processor
2. credit_balances        — Customer credit balance system (RF3)
3. spending_caps          — Customer-configurable overage spending caps (SC1)
4. dead_letter_webhooks   — Failed webhook processing queue (WH3)
5. webhook_health_stats   — Webhook health monitoring (WH2)
6. refund_audits          — Refund audit trail (RF5)

BC-001: Every table has company_id
BC-002: All money fields are DECIMAL(10,2)

Revises: 023_training_runs
"""

from alembic import op
import sqlalchemy as sa

revision = "024_day5_billing_protection"
down_revision = "023_training_runs"


def upgrade() -> None:
    # 1. chargebacks — Track chargebacks from payment processor
    op.create_table(
        "chargebacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("paddle_transaction_id", sa.String(255), nullable=True),
        sa.Column("paddle_chargeback_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("reason", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), default="received"),  # received/under_review/won/lost
        sa.Column("service_stopped_at", sa.DateTime, nullable=True),
        sa.Column("notification_sent_at", sa.DateTime, nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_chargebacks_company", "chargebacks", ["company_id"])
    op.create_index("idx_chargebacks_status", "chargebacks", ["status"])

    # 2. credit_balances — Customer credit balance system (RF3)
    op.create_table(
        "credit_balances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("amount", sa.Numeric(10, 2), default=0),  # BC-002
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("source", sa.String(30), nullable=False),  # refund/promo/goodwill/cooling_off
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("applied_to_invoice_id", sa.String(36), nullable=True),
        sa.Column("applied_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(20), default="available"),  # available/partially_used/fully_used/expired
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_credit_balances_company", "credit_balances", ["company_id"])
    op.create_index("idx_credit_balances_status", "credit_balances", ["status"])

    # 3. spending_caps — Customer-configurable overage spending caps (SC1)
    op.create_table(
        "spending_caps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("max_overage_amount", sa.Numeric(10, 2), nullable=True),  # NULL=no cap (BC-002)
        sa.Column("alert_thresholds", sa.Text, nullable=True),  # JSON: '[50,75,90]'
        sa.Column("soft_cap_alerts_sent", sa.Text, nullable=True),  # JSON: tracking sent alerts
        sa.Column("is_active", sa.Boolean, default=False),
        sa.Column("acknowledged_warning", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 4. dead_letter_webhooks — Failed webhook processing queue (WH3)
    op.create_table(
        "dead_letter_webhooks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=True, index=True),
        sa.Column("provider", sa.String(50), default="paddle"),
        sa.Column("event_id", sa.String(255), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), default="pending"),  # pending/retrying/processed/discarded
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("max_retries", sa.Integer, default=3),
        sa.Column("next_retry_at", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_dead_letter_webhooks_company", "dead_letter_webhooks", ["company_id"])
    op.create_index("idx_dead_letter_webhooks_status", "dead_letter_webhooks", ["status"])

    # 5. webhook_health_stats — Webhook health monitoring (WH2)
    op.create_table(
        "webhook_health_stats",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(50), default="paddle"),
        sa.Column("date", sa.Date, nullable=True),
        sa.Column("events_received", sa.Integer, default=0),
        sa.Column("events_processed", sa.Integer, default=0),
        sa.Column("events_failed", sa.Integer, default=0),
        sa.Column("avg_processing_time_ms", sa.Numeric(10, 2), default=0),
        sa.Column("failure_rate", sa.Numeric(5, 4), default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_webhook_health_stats_date", "webhook_health_stats", ["date"])

    # 6. refund_audits — Refund audit trail (RF5)
    op.create_table(
        "refund_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("refund_type", sa.String(20), nullable=False),  # full/partial/credit/cooling_off
        sa.Column("original_amount", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("refund_amount", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("approver_id", sa.String(36), nullable=True),
        sa.Column("approver_name", sa.String(255), nullable=True),
        sa.Column("second_approver_id", sa.String(36), nullable=True),  # for amounts > $500
        sa.Column("second_approver_name", sa.String(255), nullable=True),
        sa.Column("paddle_refund_id", sa.String(255), nullable=True),
        sa.Column("credit_balance_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),  # pending/approved/rejected/processed/failed
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_refund_audits_company", "refund_audits", ["company_id"])
    op.create_index("idx_refund_audits_status", "refund_audits", ["status"])


def downgrade() -> None:
    op.drop_table("refund_audits")
    op.drop_table("webhook_health_stats")
    op.drop_table("dead_letter_webhooks")
    op.drop_table("spending_caps")
    op.drop_table("credit_balances")
    op.drop_table("chargebacks")
