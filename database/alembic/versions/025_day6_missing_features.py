"""Day 6: Missing features tables — promo_codes, company_promo_uses, invoice_amendments, pause_records + trial columns

Revision ID: 025_day6_missing_features
Revises: 024_day5_billing_protection
Create Date: 2026-04-16

Adds:
- promo_codes table (MF3)
- company_promo_uses table (MF3)
- invoice_amendments table (MF7)
- pause_records table (MF2)
- trial_days, trial_started_at, trial_ends_at columns on subscriptions (MF1)
- billing_method column on companies (MF6)
- currency column on companies (MF4)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "025_day6_missing_features"
down_revision = "024_day5_billing_protection"
branch_labels = None
depends_on = None


def upgrade():
    # MF3: promo_codes
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("discount_type", sa.String(20), nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), server_default="0"),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("applies_to_tiers", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # MF3: company_promo_uses
    op.create_table(
        "company_promo_uses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("promo_code_id", sa.String(36), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("invoice_id", sa.String(36), nullable=True),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0.00"),
    )

    # MF7: invoice_amendments
    op.create_table(
        "invoice_amendments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_id", sa.String(36), nullable=False, index=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("original_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("new_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("amendment_type", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("paddle_credit_note_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # MF2: pause_records
    op.create_table(
        "pause_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("subscription_id", sa.String(36), nullable=False),
        sa.Column("paused_at", sa.DateTime(), nullable=False),
        sa.Column("resumed_at", sa.DateTime(), nullable=True),
        sa.Column("pause_duration_days", sa.Integer(), nullable=True),
        sa.Column("max_pause_days", sa.Integer(), server_default="30"),
        sa.Column("period_end_extension_days", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # MF1: Trial columns on subscriptions
    op.add_column(
        "subscriptions",
        sa.Column("trial_days", sa.Integer(), server_default="0", nullable=True),
    )
    op.add_column(
        "subscriptions", sa.Column("trial_started_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "subscriptions", sa.Column("trial_ends_at", sa.DateTime(), nullable=True)
    )

    # MF4: Currency on companies
    op.add_column(
        "companies",
        sa.Column("currency", sa.String(3), server_default="USD", nullable=True),
    )

    # MF6: Billing method on companies
    op.add_column(
        "companies",
        sa.Column(
            "billing_method", sa.String(20), server_default="automatic", nullable=True
        ),
    )


def downgrade():
    op.drop_column("companies", "billing_method")
    op.drop_column("companies", "currency")
    op.drop_column("subscriptions", "trial_ends_at")
    op.drop_column("subscriptions", "trial_started_at")
    op.drop_column("subscriptions", "trial_days")
    op.drop_table("pause_records")
    op.drop_table("invoice_amendments")
    op.drop_table("company_promo_uses")
    op.drop_table("promo_codes")
