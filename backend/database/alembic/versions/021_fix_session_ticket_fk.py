"""CROSS-16: Fix orphan FK references to non-existent sessions table.

The sessions table was renamed to tickets (BL01) but 14 FK constraints
across 4 migrations still reference sessions.id. This migration drops
those orphan constraints so alembic upgrade head succeeds.

Affected migrations & tables:
  003_ai_pipeline_tables  (4): gsd_sessions, confidence_scores,
                                guardrail_blocks, model_usage_logs
  004_integration_tables  (1): event_buffer
  006_analytics_onboarding (2): qa_scores, agent_mistakes
  007_remaining_gap_tables (7): approval_queues, executed_actions,
                                 classification_log,
                                 guardrails_audit_log,
                                 guardrails_blocked_queue,
                                 ai_response_feedback,
                                 human_corrections

FK naming convention: {table_name}_session_id_fkey

The session_id column itself is preserved (nullable) — only the
foreign-key constraint referencing the non-existent sessions table
is removed.

Downgrade intentionally does not restore these invalid constraints: the
parent `sessions` table was retired, and re-creating the references would
make PostgreSQL downgrades fail. Earlier migrations drop the dependent tables.
"""

from alembic import op

revision = "021_fix_session_ticket_fk"
down_revision = "020"
branch_labels = None
depends_on = None

# ── Complete inventory of orphan session_id FK constraints ──────────
# Format: (table_name, fk_constraint_name)
#
# Constraint names follow the project convention
#   {table_name}_session_id_fkey
#
ORPHAN_SESSION_FKS = [
    # 003_ai_pipeline_tables
    ("gsd_sessions", "gsd_sessions_session_id_fkey"),
    ("confidence_scores", "confidence_scores_session_id_fkey"),
    ("guardrail_blocks", "guardrail_blocks_session_id_fkey"),
    ("model_usage_logs", "model_usage_logs_session_id_fkey"),
    # 004_integration_tables
    ("event_buffer", "event_buffer_session_id_fkey"),
    # 006_analytics_onboarding_tables
    ("qa_scores", "qa_scores_session_id_fkey"),
    ("agent_mistakes", "agent_mistakes_session_id_fkey"),
    # 007_remaining_gap_tables
    ("approval_queues", "approval_queues_session_id_fkey"),
    ("executed_actions", "executed_actions_session_id_fkey"),
    ("classification_log", "classification_log_session_id_fkey"),
    ("guardrails_audit_log", "guardrails_audit_log_session_id_fkey"),
    ("guardrails_blocked_queue", "guardrails_blocked_queue_session_id_fkey"),
    ("ai_response_feedback", "ai_response_feedback_session_id_fkey"),
    ("human_corrections", "human_corrections_session_id_fkey"),
]

# The referenced (non-existent) target of every constraint
_SESSIONS_TABLE = "sessions"


def _drop_orphan_fks(conn, tables_to_process=None):
    """Drop orphan session_id FK constraints from affected tables.

    Uses batch_alter_table for SQLite compatibility.  Wrapped in
    per-table try/except so a missing constraint on a fresh database
    does not abort the entire migration.

    Args:
        conn: Alembic connection (unused but kept for signature
              consistency with op.get_bind() patterns).
        tables_to_process: Optional subset of ORPHAN_SESSION_FKS to
            process.  Defaults to the full list.
    """
    targets = tables_to_process if tables_to_process is not None else ORPHAN_SESSION_FKS

    from sqlalchemy import inspect

    inspector = inspect(conn)
    for table_name, fk_name in targets:
        # Fresh installations no longer create these obsolete references to
        # the retired sessions table. Inspect first: on PostgreSQL, attempting
        # to drop a missing constraint aborts the whole migration transaction,
        # even when the exception is caught in Python.
        if not inspector.has_table(table_name):
            continue
        existing_names = {
            fk.get("name") for fk in inspector.get_foreign_keys(table_name)
        }
        if fk_name not in existing_names:
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        # Refresh after SQLite batch table recreation / PostgreSQL DDL.
        inspector = inspect(conn)


# ── Alembic callbacks ────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()
    _drop_orphan_fks(conn)


def downgrade() -> None:
    # These foreign keys targeted a table that no longer exists. Do not
    # recreate them; the earlier table migrations remove the affected tables.
    pass
