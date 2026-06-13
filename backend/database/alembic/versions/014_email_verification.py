"""014_email_verification: Email verification tokens & flow

Revision ID: 014_email_verification
Revises: 013_email_verification_settings
Create Date: 2026-04-12

Adds email verification token infrastructure:
- email_verification_tokens for secure email verification
- Tracks verification status per user email
"""

from alembic import op
import sqlalchemy as sa


revision = "014_email_verification"
down_revision = "013_email_verification_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create email verification tokens table."""
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        # Email being verified
        sa.Column("email", sa.String(255), nullable=False, index=True),
        # SHA-256 hashed verification token
        sa.Column("token_hash", sa.String(64), nullable=False),
        # Verification status
        sa.Column("verified", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("verified_at", sa.DateTime, nullable=True),
        # Token expiry (24 hours)
        sa.Column("expires_at", sa.DateTime, nullable=False),
        # Attempt tracking
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    # Index for efficient lookup by email + company + unverified
    op.create_index(
        "ix_email_ver_token_email_company",
        "email_verification_tokens",
        ["email", "company_id"],
    )
    op.create_index(
        "ix_email_ver_token_unverified",
        "email_verification_tokens",
        ["email", "company_id", "verified", "expires_at"],
    )


def downgrade() -> None:
    """Drop email verification tokens table."""
    op.drop_index("ix_email_ver_token_unverified", table_name="email_verification_tokens")
    op.drop_index("ix_email_ver_token_email_company", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
