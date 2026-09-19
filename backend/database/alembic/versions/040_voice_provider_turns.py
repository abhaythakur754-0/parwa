"""Voice BYO provider + conversation turns

BYO model (2026-02): Parwa never provisions phone numbers or pays for
telecom. Tenants connect their OWN calling provider account and pay that
provider directly.

- voice_channel_configs.provider        VARCHAR(30) NOT NULL DEFAULT 'twilio'
- voice_channel_configs.number_source   DEFAULT changed to 'bring_own'
                                        (parwa_provided retired; existing
                                        rows migrated to 'bring_own')
- NEW TABLE voice_call_turns            append-only live-call transcript
                                        (customer / agent / tool records)

Revision ID: 040_voice_provider_turns
Revises: 039_ticket_list_indexes
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "040_voice_provider_turns"
down_revision = "039_ticket_list_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0. CRITICAL: number_source was NEVER created by any earlier migration
    #    (it existed only on the model). 040 previously crashed here on every
    #    fresh `upgrade head`, blocking ALL later migrations. Create it first.
    op.execute(
        "ALTER TABLE voice_channel_configs ADD COLUMN IF NOT EXISTS number_source "
        "VARCHAR(20) NOT NULL DEFAULT 'parwa_provided'"
    )

    # 1. provider column on voice_channel_configs
    op.add_column(
        "voice_channel_configs",
        sa.Column(
            "provider",
            sa.String(length=30),
            nullable=False,
            server_default="twilio",
        ),
    )

    # 2. retire parwa_provided: migrate legacy rows + new default
    op.execute(
        "UPDATE voice_channel_configs SET number_source = 'bring_own' "
        "WHERE number_source <> 'bring_own'"
    )
    op.alter_column(
        "voice_channel_configs",
        "number_source",
        existing_type=sa.String(length=20),
        server_default="bring_own",
    )

    # 3. per-turn transcript table
    op.create_table(
        "voice_call_turns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "call_id",
            sa.String(length=36),
            sa.ForeignKey("voice_calls.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("call_sid", sa.String(length=64), nullable=True, index=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="customer"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("tool_id", sa.String(length=200), nullable=True),
        sa.Column("tool_status", sa.String(length=30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "role IN ('customer','agent','system')",
            name="ck_voice_turn_role",
        ),
        sa.CheckConstraint(
            "tool_status IS NULL OR tool_status IN "
            "('ok','failed','timeout','refused')",
            name="ck_voice_turn_tool_status",
        ),
    )
    op.create_index(
        "ix_voice_turns_call_sid",
        "voice_call_turns",
        ["company_id", "call_sid", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_voice_turns_call_sid", table_name="voice_call_turns")
    op.drop_table("voice_call_turns")
    op.alter_column(
        "voice_channel_configs",
        "number_source",
        existing_type=sa.String(length=20),
        server_default="parwa_provided",
    )
    op.drop_column("voice_channel_configs", "provider")
