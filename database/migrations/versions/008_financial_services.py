"""
Financial Services Database Migration.

Creates tables for:
- Financial audit trail
- Compliance records
- Fraud alerts
- Complaint tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Financial audit trail table
    op.create_table(
        "financial_audit_trail",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("customer_id", sa.String(50), nullable=False),
        sa.Column("account_id", sa.String(50), nullable=True),
        sa.Column("transaction_id", sa.String(50), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("justification", sa.Text, nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("previous_state", postgresql.JSONB, nullable=True),
        sa.Column("new_state", postgresql.JSONB, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
    )

    op.create_index(
        "ix_financial_audit_trail_customer",
        "financial_audit_trail",
        ["customer_id", "timestamp"]
    )
    op.create_index(
        "ix_financial_audit_trail_actor",
        "financial_audit_trail",
        ["actor", "timestamp"]
    )

    # Compliance records table
    op.create_table(
        "compliance_records",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("violations", postgresql.JSONB, default=[]),
        sa.Column("warnings", postgresql.JSONB, default=[]),
        sa.Column("recommendations", postgresql.JSONB, default=[]),
        sa.Column("audit_id", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
    )

    # Fraud alerts table
    op.create_table(
        "fraud_alerts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_id", sa.String(50), unique=True, nullable=False),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 4)),
        sa.Column("customer_id", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("factors", postgresql.JSONB, default=[]),
        sa.Column("transaction_ids", postgresql.JSONB, default=[]),
        sa.Column("investigation_status", sa.String(20), default="pending"),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
    )

    op.create_index(
        "ix_fraud_alerts_status",
        "fraud_alerts",
        ["investigation_status", "risk_level"]
    )

    # Complaint tracking table
    op.create_table(
        "complaint_tracking",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("complaint_id", sa.String(50), unique=True, nullable=False),
        sa.Column("customer_id", sa.String(50), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_account", sa.String(50), nullable=False),
        sa.Column("complaint_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("products_services", postgresql.JSONB, default=[]),
        sa.Column("associated_persons", postgresql.JSONB, default=[]),
        sa.Column("status", sa.String(20), default="open"),
        sa.Column("resolution_description", sa.Text, nullable=True),
        sa.Column("supervisory_reviewer", sa.String(255), nullable=True),
        sa.Column("complaint_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("receipt_date", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolution_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supervisory_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
    )

    op.create_index(
        "ix_complaint_tracking_status",
        "complaint_tracking",
        ["status", "receipt_date"]
    )


def downgrade() -> None:
    op.drop_table("complaint_tracking")
    op.drop_table("fraud_alerts")
    op.drop_table("compliance_records")
    op.drop_table("financial_audit_trail")
