"""Alembic migration 039: Ticket list composite indexes.

1M-request readiness: the two hottest dashboard queries are
  - list tickets for tenant, newest first  (company_id, created_at DESC)
  - list tickets for tenant by status      (company_id, status)
Single-column company_id index exists but forces a sort / wider scan as
ticket volume grows. Composite indexes let PostgreSQL serve filter+sort
(and the per-request COUNT) straight from the index.

Idempotent: guarded with an index-exists check so startup migrations
can re-run safely without crashing the service.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "039_ticket_list_indexes"
down_revision = "038_superglue_action_safety"
branch_labels = None
depends_on = None


def _index_exists(conn, table: str, name: str) -> bool:
    """Guard so startup migrations never crash on a re-run."""
    from sqlalchemy import inspect

    inspector = inspect(conn)
    return name in [ix["name"] for ix in inspector.get_indexes(table)]


def upgrade() -> None:
    conn = op.get_bind()
    if not _index_exists(conn, "tickets", "ix_tickets_company_created_at"):
        op.create_index(
            "ix_tickets_company_created_at",
            "tickets",
            [sa.text("company_id"), sa.text("created_at DESC")],
        )
    if not _index_exists(conn, "tickets", "ix_tickets_company_status"):
        op.create_index(
            "ix_tickets_company_status",
            "tickets",
            ["company_id", "status"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _index_exists(conn, "tickets", "ix_tickets_company_created_at"):
        op.drop_index("ix_tickets_company_created_at", table_name="tickets")
    if _index_exists(conn, "tickets", "ix_tickets_company_status"):
        op.drop_index("ix_tickets_company_status", table_name="tickets")
