"""021_agent_metrics_tables: agent_metrics_daily, agent_performance_alerts,
agent_metric_thresholds

F-098: Agent Performance Metrics
Revises: 020_custom_integrations
"""

from alembic import op
import sqlalchemy as sa

revision = "021_agent_metrics_tables"
down_revision = "020_custom_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_metrics_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("tickets_handled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("resolved_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("escalated_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("avg_csat", sa.Numeric(3, 1), nullable=True),
        sa.Column("avg_handle_time_seconds", sa.Integer, nullable=True),
        sa.Column("resolution_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("escalation_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "agent_id",
            "date",
            name="uq_agent_metrics_daily_agent_date",
        ),
    )
    op.create_index(
        "ix_agent_metrics_daily_company_date",
        "agent_metrics_daily",
        ["company_id", "date"],
    )

    op.create_table(
        "agent_performance_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("metric_name", sa.String(50), nullable=False),
        sa.Column("current_value", sa.Numeric(5, 2), nullable=True),
        sa.Column("threshold_value", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "consecutive_days_below",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "triggered_training",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime, nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "status IN ('active','acknowledged','resolved')",
            name="ck_agent_performance_alert_status",
        ),
    )
    op.create_index(
        "ix_agent_performance_alerts_company_status",
        "agent_performance_alerts",
        ["company_id", "status"],
    )

    op.create_table(
        "agent_metric_thresholds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "resolution_rate_min",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="70.00",
        ),
        sa.Column(
            "confidence_min",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="65.00",
        ),
        sa.Column(
            "csat_min",
            sa.Numeric(3, 1),
            nullable=False,
            server_default="3.5",
        ),
        sa.Column(
            "escalation_max_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="15.00",
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_id",
            "agent_id",
            name="uq_agent_metric_thresholds_company_agent",
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_metric_thresholds")
    op.drop_table("agent_performance_alerts")
    op.drop_table("agent_metrics_daily")
