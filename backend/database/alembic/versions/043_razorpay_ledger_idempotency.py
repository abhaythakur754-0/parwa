"""Make Razorpay billing ledger writes idempotent.

Revision ID: 043_razorpay_ledger_idempotency
Revises: 042_rls_and_view_security
"""
from alembic import op
import sqlalchemy as sa

revision = "043_razorpay_ledger_idempotency"
down_revision = "042_rls_and_view_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older webhook retries may already have produced duplicate ledger rows.
    # Keep the oldest row per provider ID before enforcing uniqueness.
    op.execute(
        """
        DELETE FROM invoices
        WHERE paddle_invoice_id IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM invoices
              WHERE paddle_invoice_id IS NOT NULL
              GROUP BY paddle_invoice_id
          )
        """
    )
    op.execute(
        """
        DELETE FROM transactions
        WHERE paddle_transaction_id IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM transactions
              WHERE paddle_transaction_id IS NOT NULL
              GROUP BY paddle_transaction_id
          )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_provider_invoice_id "
        "ON invoices (paddle_invoice_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_provider_transaction_id "
        "ON transactions (paddle_transaction_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_transactions_provider_transaction_id")
    op.execute("DROP INDEX IF EXISTS uq_invoices_provider_invoice_id")
