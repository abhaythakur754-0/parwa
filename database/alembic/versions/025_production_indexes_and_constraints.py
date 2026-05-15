"""Production indexes and constraints

Revision ID: 025
Revises: 024
Create Date: 2025-01-15 00:00:00.000000

- Add UniqueConstraint on customers(company_id, email)
- Add composite indexes on tickets for common query patterns
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint on customers table
    op.create_unique_constraint(
        'uq_customer_company_email',
        'customers',
        ['company_id', 'email'],
    )

    # Add composite indexes on tickets table
    op.create_index(
        'ix_tickets_company_status',
        'tickets',
        ['company_id', 'status'],
    )
    op.create_index(
        'ix_tickets_company_created',
        'tickets',
        ['company_id', 'created_at'],
    )
    op.create_index(
        'ix_tickets_company_assignee',
        'tickets',
        ['company_id', 'assigned_to'],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_tickets_company_assignee', table_name='tickets')
    op.drop_index('ix_tickets_company_created', table_name='tickets')
    op.drop_index('ix_tickets_company_status', table_name='tickets')

    # Drop unique constraint
    op.drop_constraint('uq_customer_company_email', 'customers', type_='unique')
