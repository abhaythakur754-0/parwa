"""Add unique_id column to companies table

Revision ID: 030_company_unique_id
Revises: 029_voice_channel_tables
Create Date: 2026-07-04

Adds a user-chosen unique identifier to each company.
This is set during onboarding Step 1 and shown on the dashboard.
"""
from alembic import op
import sqlalchemy as sa

revision = "030_company_unique_id"
down_revision = "029_voice_channel_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("unique_id", sa.String(50), nullable=True))
    op.create_index("ix_companies_unique_id", "companies", ["unique_id"], unique=True)


def downgrade():
    op.drop_index("ix_companies_unique_id", table_name="companies")
    op.drop_column("companies", "unique_id")
