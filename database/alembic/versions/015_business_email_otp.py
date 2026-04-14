"""Add business_email_otps table

Week 6 Day 10-11: Business Email OTP Verification

Creates table for storing OTP codes sent to verify business emails.
- 6-digit OTP codes
- SHA-256 hashed for security
- 10 minute expiry
- Rate limiting (3 requests per hour)
- Max 5 verification attempts

Revision ID: 015_business_email_otp
Revises: 014_email_verification
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015_business_email_otp'
down_revision = '014_email_verification'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create business_email_otps table."""
    op.create_table(
        'business_email_otps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('code_hash', sa.String(64), nullable=False),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
    )
    
    # Create indexes for efficient queries
    op.create_index('ix_business_email_otps_email_company', 'business_email_otps', ['email', 'company_id'])
    op.create_index('ix_business_email_otps_unverified', 'business_email_otps', ['email', 'company_id', 'verified', 'expires_at'])


def downgrade() -> None:
    """Drop business_email_otps table."""
    op.drop_index('ix_business_email_otps_unverified', table_name='business_email_otps')
    op.drop_index('ix_business_email_otps_email_company', table_name='business_email_otps')
    op.drop_table('business_email_otps')
