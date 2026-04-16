"""023_training_runs: F-100 Agent Lightning Training Loop + F-101 50-Mistake Threshold

Creates training_runs table with full orchestration support.

Revises: 022_agent_provisioning
"""

from alembic import op
import sqlalchemy as sa

revision = "023_training_runs"
down_revision = "022_agent_provisioning"


def upgrade() -> None:
    # training_runs table
    op.create_table(
        "training_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id", sa.String(36),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("training_datasets.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("base_model", sa.String(100), nullable=True),
        sa.Column(
            "status", sa.String(30), nullable=False,
            server_default="queued",
        ),
        sa.Column("progress_pct", sa.Integer, default=0),
        sa.Column("current_epoch", sa.Integer, default=0),
        sa.Column("total_epochs", sa.Integer, default=3),
        sa.Column("metrics", sa.JSON, nullable=True),
        sa.Column("checkpoint_path", sa.Text, nullable=True),
        sa.Column("model_path", sa.Text, nullable=True),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("instance_id", sa.String(100), nullable=True),
        sa.Column("gpu_type", sa.String(50), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 2), default=0),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_training_runs_company", "training_runs", ["company_id"])
    op.create_index("ix_training_runs_agent", "training_runs", ["agent_id"])
    op.create_index("ix_training_runs_status", "training_runs", ["status"])

    # training_samples table (F-103)
    op.create_table(
        "training_samples",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_id", sa.String(36),
            sa.ForeignKey("training_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticket_id", sa.String(36), nullable=True),
        sa.Column("instruction", sa.Text, nullable=False),
        sa.Column("input_text", sa.Text, nullable=True),
        sa.Column("output", sa.Text, nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column(
            "quality_flag", sa.String(20), nullable=False,
            server_default="valid",
        ),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_training_samples_dataset", "training_samples", ["dataset_id"])
    op.create_index("ix_training_samples_company", "training_samples", ["company_id"])

    # Update training_checkpoints to add new columns
    op.add_column("training_checkpoints", "s3_path", sa.Text, nullable=True)
    op.add_column("training_checkpoints", "loss", sa.Float, nullable=True)
    op.add_column("training_checkpoints", "accuracy", sa.Float, nullable=True)
    op.add_column("training_checkpoints", "metrics", sa.JSON, nullable=True)

    # Update training_datasets with new columns
    op.add_column("training_datasets", "quality_score", sa.Float, nullable=True)
    op.add_column("training_datasets", "category_distribution", sa.JSON, nullable=True)
    op.add_column("training_datasets", "s3_path", sa.Text, nullable=True)
    op.add_column("training_datasets", "agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=True)


def downgrade() -> None:
    op.drop_column("training_datasets", "s3_path")
    op.drop_column("training_datasets", "category_distribution")
    op.drop_column("training_datasets", "quality_score")
    op.drop_column("training_datasets", "agent_id")
    op.drop_column("training_checkpoints", "metrics")
    op.drop_column("training_checkpoints", "accuracy")
    op.drop_column("training_checkpoints", "loss")
    op.drop_column("training_checkpoints", "s3_path")
    op.drop_table("training_samples")
    op.drop_index("ix_training_runs_status", table_name="training_runs")
    op.drop_index("ix_training_runs_agent", table_name="training_runs")
    op.drop_index("ix_training_runs_company", table_name="training_runs")
    op.drop_table("training_runs")
