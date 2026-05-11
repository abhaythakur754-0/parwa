"""
Billing Extended Tables Migration (009)

Creates 8 new tables for extended billing functionality:
1. client_refunds - PARWA clients refunding THEIR customers
2. payment_methods - Payment method cache from Paddle
3. usage_records - Daily/monthly usage tracking
4. variant_limits - Variant feature limits
5. idempotency_keys - Webhook idempotency tracking
6. webhook_sequences - Webhook ordering tracking
7. proration_audits - Proration calculation audit trail
8. payment_failures - Payment failure audit log

BC-001: Every table has company_id
BC-002: All money fields are DECIMAL(10,2)
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. client_refunds - PARWA clients refunding THEIR customers
    op.create_table(
        "client_refunds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id"), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), default="pending"),  # pending/processed/failed
        sa.Column("external_ref", sa.String(255), nullable=True),  # Client's payment system ref
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_client_refunds_company", "client_refunds", ["company_id"])
    op.create_index("idx_client_refunds_status", "client_refunds", ["status"])

    # 2. payment_methods - Payment method cache from Paddle
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("paddle_payment_method_id", sa.String(255), nullable=False),
        sa.Column("method_type", sa.String(20)),  # card/paypal/wire/apple_pay/google_pay
        sa.Column("last_four", sa.String(4)),
        sa.Column("expiry_month", sa.Integer),
        sa.Column("expiry_year", sa.Integer),
        sa.Column("card_brand", sa.String(20)),  # visa/mastercard/amex/etc
        sa.Column("is_default", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_payment_methods_company", "payment_methods", ["company_id"])
    op.create_index(
        "idx_payment_methods_paddle_id",
        "payment_methods",
        ["paddle_payment_method_id"],
        unique=True,
    )

    # 3. usage_records - Daily/monthly usage tracking
    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("record_date", sa.Date, nullable=False),
        sa.Column("record_month", sa.String(7), nullable=False),  # YYYY-MM
        sa.Column("tickets_used", sa.Integer, default=0),
        sa.Column("ai_agents_used", sa.Integer, default=0),
        sa.Column("voice_minutes_used", sa.Numeric(10, 2), default=0),  # BC-002
        sa.Column("overage_tickets", sa.Integer, default=0),
        sa.Column("overage_charges", sa.Numeric(10, 2), default=0),  # BC-002
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        # Unique constraint: one record per company per day
        sa.UniqueConstraint("company_id", "record_date", name="uq_usage_records_company_date"),
    )
    op.create_index("idx_usage_records_company", "usage_records", ["company_id"])
    op.create_index("idx_usage_records_month", "usage_records", ["record_month"])

    # 4. variant_limits - Variant feature limits cache
    op.create_table(
        "variant_limits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("variant_name", sa.String(50), unique=True, nullable=False),  # starter/growth/high
        sa.Column("monthly_tickets", sa.Integer, nullable=False),
        sa.Column("ai_agents", sa.Integer, nullable=False),
        sa.Column("team_members", sa.Integer, nullable=False),
        sa.Column("voice_slots", sa.Integer, nullable=False),
        sa.Column("kb_docs", sa.Integer, nullable=False),
        sa.Column("price_monthly", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Insert default variant limits
    op.execute("""
        INSERT INTO variant_limits (id, variant_name, monthly_tickets, ai_agents, team_members, voice_slots, kb_docs, price_monthly)
        VALUES
            ('variant-starter-001', 'starter', 2000, 1, 3, 0, 100, 999.00),
            ('variant-growth-001', 'growth', 5000, 3, 10, 2, 500, 2499.00),
            ('variant-high-001', 'high', 15000, 5, 25, 5, 2000, 3999.00)
    """)

    # 5. idempotency_keys - Webhook idempotency tracking
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(255), unique=True, nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),  # paddle_webhook, stripe_webhook, etc
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("request_body_hash", sa.String(64), nullable=True),  # SHA-256 hash
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_idempotency_keys_key", "idempotency_keys", ["idempotency_key"])
    op.create_index("idx_idempotency_keys_expires", "idempotency_keys", ["expires_at"])

    # 6. webhook_sequences - Webhook ordering tracking
    op.create_table(
        "webhook_sequences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("paddle_event_id", sa.String(255), unique=True, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("processing_order", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), default="pending"),  # pending/processing/processed/failed
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_webhook_sequences_company", "webhook_sequences", ["company_id"])
    op.create_index("idx_webhook_sequences_event", "webhook_sequences", ["paddle_event_id"])
    op.create_index("idx_webhook_sequences_status", "webhook_sequences", ["status"])

    # 7. proration_audits - Proration calculation audit trail
    op.create_table(
        "proration_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("old_variant", sa.String(50), nullable=False),
        sa.Column("new_variant", sa.String(50), nullable=False),
        sa.Column("old_price", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("new_price", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("days_remaining", sa.Integer, nullable=False),
        sa.Column("days_in_period", sa.Integer, nullable=False),
        sa.Column("unused_amount", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("proration_amount", sa.Numeric(10, 2), nullable=False),  # BC-002
        sa.Column("credit_applied", sa.Numeric(10, 2), default=0),  # BC-002
        sa.Column("charge_applied", sa.Numeric(10, 2), default=0),  # BC-002
        sa.Column("billing_cycle_start", sa.Date, nullable=False),
        sa.Column("billing_cycle_end", sa.Date, nullable=False),
        sa.Column("calculated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_proration_audits_company", "proration_audits", ["company_id"])

    # 8. payment_failures - Payment failure audit log
    op.create_table(
        "payment_failures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("paddle_subscription_id", sa.String(255), nullable=True),
        sa.Column("paddle_transaction_id", sa.String(255), nullable=True),
        sa.Column("failure_code", sa.String(50), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("amount_attempted", sa.Numeric(10, 2), nullable=True),  # BC-002
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("service_stopped_at", sa.DateTime, nullable=True),
        sa.Column("service_resumed_at", sa.DateTime, nullable=True),
        sa.Column("notification_sent", sa.Boolean, default=False),
        sa.Column("resolved", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_payment_failures_company", "payment_failures", ["company_id"])
    op.create_index("idx_payment_failures_subscription", "payment_failures", ["paddle_subscription_id"])


def downgrade() -> None:
    op.drop_table("payment_failures")
    op.drop_table("proration_audits")
    op.drop_table("webhook_sequences")
    op.drop_table("idempotency_keys")
    op.drop_table("variant_limits")
    op.drop_table("usage_records")
    op.drop_table("payment_methods")
    op.drop_table("client_refunds")
