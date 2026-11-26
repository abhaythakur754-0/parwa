"""Add tenant ownership and RLS to agent assignments.

The original 011 migration created ai_agent_assignments as a global table.
The ORM/service layer now treats assignments as tenant-owned. Add the
nullable tenant key so existing global rows remain safely unassigned while
all new service-created rows are scoped to a company.
"""
from alembic import op
import sqlalchemy as sa

revision = "045_agent_assignment_tenant_scope"
down_revision = "044_emergency_state_pause"
branch_labels = None
depends_on = None

TABLE = "ai_agent_assignments"
POLICIES = {
    "tenant_select": (
        "FOR SELECT USING (company_id = app.current_tenant_id())"
    ),
    "tenant_insert": (
        "FOR INSERT WITH CHECK (company_id = app.current_tenant_id())"
    ),
    "tenant_update": (
        "FOR UPDATE USING (company_id = app.current_tenant_id())"
    ),
    "tenant_delete": (
        "FOR DELETE USING (company_id = app.current_tenant_id())"
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE):
        raise RuntimeError(f"Expected {TABLE} table before applying tenant scope")

    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    foreign_keys = inspector.get_foreign_keys(TABLE)
    indexes = {index["name"] for index in inspector.get_indexes(TABLE)}

    has_company_fk = any(
        fk.get("referred_table") == "companies"
        and fk.get("constrained_columns") == ["company_id"]
        for fk in foreign_keys
    )
    has_company_index = "ix_ai_agent_assignments_company_id" in indexes

    with op.batch_alter_table(TABLE) as batch:
        if "company_id" not in columns:
            batch.add_column(sa.Column("company_id", sa.String(36), nullable=True))
        if not has_company_fk:
            batch.create_foreign_key(
                "fk_ai_agent_assignments_company_id",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="CASCADE",
            )
        if not has_company_index:
            batch.create_index(
                "ix_ai_agent_assignments_company_id",
                ["company_id"],
                unique=False,
            )

    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY"))
        for suffix, clause in POLICIES.items():
            policy_name = f"{TABLE}_{suffix}"
            bind.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {TABLE}"))
            bind.execute(sa.text(
                f"CREATE POLICY {policy_name} ON {TABLE} {clause}"
            ))

        unscoped_count = bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {TABLE} WHERE company_id IS NULL"
        )).scalar_one()
        if unscoped_count:
            # Legacy global rows remain inaccessible to tenant roles under RLS.
            # Tenant services always create new rows with an authenticated company_id.
            import logging
            logging.getLogger("alembic").warning(
                "%d legacy %s rows remain unscoped and are hidden by tenant RLS",
                unscoped_count,
                TABLE,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for suffix in POLICIES:
            policy_name = f"{TABLE}_{suffix}"
            bind.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {TABLE}"))
        bind.execute(sa.text(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY"))

    # Keep company_id, its FK and index on downgrade to avoid discarding
    # tenant ownership data created after this migration.
