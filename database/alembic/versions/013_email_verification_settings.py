"""013_email_verification_settings: Email verification settings & tokens

Revision ID: 013_email_verification_settings
Revises: 012
Create Date: 2026-04-12

Adds email verification infrastructure:
- verification_tokens table for email verification flow
- company email verification settings
"""

from alembic import op
import sqlalchemy as sa


revision = "013_email_verification_settings"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create email verification settings table."""
    op.create_table(
        "email_verification_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        # Whether business email verification is required
        sa.Column("require_verification", sa.Boolean, nullable=False, server_default="0"),
        # Allowed email domains for business verification
        sa.Column("allowed_domains", sa.Text, server_default="[]"),
        # Auto-verify company domain emails
        sa.Column("auto_verify_company_domain", sa.Boolean, nullable=False, server_default="0"),
        # Company domain extracted from company name/website
        sa.Column("company_domain", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_email_ver_settings_company",
        "email_verification_settings",
        ["company_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop email verification settings table."""
    op.drop_index("ix_email_ver_settings_company", table_name="email_verification_settings")
    op.drop_table("email_verification_settings")
