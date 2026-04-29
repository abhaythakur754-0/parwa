"""011_phase3_variant_engine: 9 tables for Phase 3 AI Engine

Revision ID: 011
Revises: 010
Create Date: 2026-04-06

Phase 3 Week 8 Day 1: AI Engine Foundation
- variant_ai_capabilities: Feature → variant tier mapping
- variant_instances: Unlimited variant instances per tenant
- variant_workload_distribution: Ticket assignment tracking
- ai_agent_assignments: Build agent → feature ownership
- technique_caches: Query-similarity-based caching
- ai_token_budgets: Per-tenant/instance token limits
- prompt_injection_attempts: Injection logging
- ai_performance_variant_metrics: Per-instance metrics
- pipeline_state_snapshots: LangGraph state persistence

BC-001: Every tenant-scoped table has company_id.
BC-002: Money fields use Numeric. No Float for money.
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── variant_instances (created first — FK target) ──
    op.create_table(
        "variant_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("instance_name", sa.String(255), nullable=False),
        sa.Column("variant_type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            server_default="active",
        ),
        sa.Column(
            "channel_assignment",
            sa.Text,
            server_default="[]",
        ),
        sa.Column(
            "capacity_config",
            sa.Text,
            server_default="{}",
        ),
        sa.Column("celery_queue_namespace", sa.String(100)),
        sa.Column("redis_partition_key", sa.String(100)),
        sa.Column(
            "active_tickets_count",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "total_tickets_handled",
            sa.Integer,
            server_default="0",
        ),
        sa.Column("last_activity_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_var_inst_comp_type",
        "variant_instances",
        ["company_id", "variant_type"],
    )
    op.create_index(
        "ix_var_inst_comp_status",
        "variant_instances",
        ["company_id", "status"],
    )

    # ── variant_ai_capabilities ──
    op.create_table(
        "variant_ai_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("variant_type", sa.String(50), nullable=False),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
        ),
        sa.Column("feature_id", sa.String(100), nullable=False),
        sa.Column(
            "feature_name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column("feature_category", sa.String(100)),
        sa.Column("technique_tier", sa.String(10), nullable=True),
        sa.Column(
            "is_enabled",
            sa.Boolean,
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "config_json",
            sa.Text,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_var_cap_comp_variant",
        "variant_ai_capabilities",
        ["company_id", "variant_type"],
    )
    op.create_index(
        "ix_var_cap_comp_feature",
        "variant_ai_capabilities",
        ["company_id", "feature_id"],
    )
    op.create_unique_constraint(
        "uq_var_cap_instance_feature",
        "variant_ai_capabilities",
        ["company_id", "variant_type", "instance_id", "feature_id"],
    )

    # ── variant_workload_distribution ──
    op.create_table(
        "variant_workload_distribution",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "ticket_id",
            sa.String(36),
            sa.ForeignKey("tickets.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("distribution_strategy", sa.String(50)),
        sa.Column("assigned_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            server_default="assigned",
        ),
        sa.Column(
            "escalation_target_instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
        ),
        sa.Column(
            "rebalance_from_instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
        ),
        sa.Column(
            "billing_charged_to_instance",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_vwd_inst_assigned",
        "variant_workload_distribution",
        ["company_id", "instance_id", "assigned_at"],
    )

    # ── ai_agent_assignments (global — no company_id) ──
    op.create_table(
        "ai_agent_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("agent_role", sa.String(100)),
        sa.Column(
            "feature_ids",
            sa.Text,
            server_default="[]",
        ),
        sa.Column(
            "task_ids",
            sa.Text,
            server_default="[]",
        ),
        sa.Column(
            "status",
            sa.String(50),
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )

    # ── technique_caches ──
    op.create_table(
        "technique_caches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "technique_id",
            sa.String(50),
            nullable=False,
            index=True,
        ),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column(
            "signal_profile_hash",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "cached_result",
            sa.Text,
            nullable=False,
        ),
        sa.Column(
            "similarity_score",
            sa.Numeric(5, 4),
            nullable=True,
        ),
        sa.Column(
            "hit_count",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "ttl_expires_at",
            sa.DateTime,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_tech_cache_comp_tech_qh",
        "technique_caches",
        ["company_id", "technique_id", "query_hash"],
    )
    op.create_unique_constraint(
        "uq_tech_cache_instance",
        "technique_caches",
        ["company_id", "instance_id", "technique_id", "query_hash"],
    )

    # ── ai_token_budgets ──
    op.create_table(
        "ai_token_budgets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("budget_type", sa.String(20), nullable=False),
        sa.Column("budget_period", sa.String(20), nullable=False),
        sa.Column("max_tokens", sa.Integer, nullable=False),
        sa.Column(
            "used_tokens",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "alert_threshold_pct",
            sa.Integer,
            server_default="80",
        ),
        sa.Column(
            "alert_sent",
            sa.Boolean,
            server_default="0",
        ),
        sa.Column(
            "hard_stop",
            sa.Boolean,
            server_default="1",
        ),
        sa.Column(
            "status",
            sa.String(50),
            server_default="active",
        ),
        sa.Column(
            "variant_default_limits",
            sa.Text,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_tok_bud_comp_type_per",
        "ai_token_budgets",
        ["company_id", "budget_type", "budget_period"],
    )
    op.create_unique_constraint(
        "uq_tok_bud_inst_period",
        "ai_token_budgets",
        ["company_id", "instance_id", "budget_type", "budget_period"],
    )

    # ── prompt_injection_attempts ──
    op.create_table(
        "prompt_injection_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "pattern_type",
            sa.String(100),
            nullable=False,
        ),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "query_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column("query_preview", sa.Text, nullable=True),
        sa.Column("detection_method", sa.String(100)),
        sa.Column(
            "action_taken",
            sa.String(50),
            server_default="logged",
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_inj_comp_pattern",
        "prompt_injection_attempts",
        ["company_id", "pattern_type"],
    )
    op.create_index(
        "ix_inj_comp_created",
        "prompt_injection_attempts",
        ["company_id", "created_at"],
    )

    # ── ai_performance_variant_metrics ──
    op.create_table(
        "ai_performance_variant_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("metric_date", sa.Date, nullable=False),
        sa.Column("metric_hour", sa.Integer, nullable=True),
        sa.Column(
            "total_queries",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "successful_queries",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "failed_queries",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "avg_latency_ms",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "p95_latency_ms",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "total_tokens_used",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "total_cost_usd",
            sa.Numeric(10, 4),
            server_default="0",
        ),
        sa.Column(
            "avg_confidence_score",
            sa.Numeric(5, 2),
            nullable=True,
        ),
        sa.Column(
            "error_rate_pct",
            sa.Numeric(5, 2),
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_aipvm_inst_date",
        "ai_performance_variant_metrics",
        ["company_id", "instance_id", "metric_date"],
    )
    op.create_unique_constraint(
        "uq_aipvm_inst_date_hour",
        "ai_performance_variant_metrics",
        ["company_id", "instance_id", "metric_date", "metric_hour"],
    )

    # ── pipeline_state_snapshots ──
    op.create_table(
        "pipeline_state_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("variant_instances.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "ticket_id",
            sa.String(36),
            sa.ForeignKey("tickets.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column(
            "current_node",
            sa.String(100),
            nullable=False,
        ),
        sa.Column("state_data", sa.Text, nullable=False),
        sa.Column(
            "technique_stack",
            sa.Text,
            server_default="[]",
        ),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column(
            "token_count",
            sa.Integer,
            server_default="0",
        ),
        sa.Column(
            "snapshot_type",
            sa.String(50),
            server_default="auto",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pss_ticket_created",
        "pipeline_state_snapshots",
        ["company_id", "ticket_id", "created_at"],
    )


def downgrade() -> None:
    # Drop in reverse order (respect FKs)
    op.drop_table("pipeline_state_snapshots")
    op.drop_table("ai_performance_variant_metrics")
    op.drop_table("prompt_injection_attempts")
    op.drop_table("ai_token_budgets")
    op.drop_table("technique_caches")
    op.drop_table("ai_agent_assignments")
    op.drop_table("variant_workload_distribution")
    op.drop_table("variant_ai_capabilities")
    op.drop_table("variant_instances")
