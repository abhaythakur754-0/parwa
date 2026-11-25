"""Regression coverage for migration 040 on SQLite and partially upgraded schemas."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, String, create_engine, inspect, text


_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "alembic"
    / "versions"
    / "040_voice_provider_turns.py"
)
_SPEC = importlib.util.spec_from_file_location("migration_040", _MIGRATION_PATH)
_MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MIGRATION)


def test_voice_provider_migration_supports_sqlite_and_existing_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE companies (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE voice_calls (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE voice_channel_configs ("
                "id VARCHAR(36) PRIMARY KEY, company_id VARCHAR(36), "
                "twilio_account_sid VARCHAR(64), "
                "twilio_auth_token_encrypted TEXT, twilio_phone_number VARCHAR(30))"
            )
        )
        connection.execute(text("INSERT INTO companies (id) VALUES ('co-1')"))
        connection.execute(
            text(
                "INSERT INTO voice_channel_configs "
                "(id, company_id, twilio_account_sid, twilio_auth_token_encrypted, twilio_phone_number) "
                "VALUES ('cfg-1', 'co-1', 'acct', 'encrypted', '+10000000000')"
            )
        )

        with Operations.context(MigrationContext.configure(connection)):
            _MIGRATION.upgrade()

        columns = {column["name"] for column in inspect(connection).get_columns("voice_channel_configs")}
        expected = {
            "number_source",
            "caller_id_name",
            "greeting_style",
            "language_preference",
            "parwa_phone_number",
            "parwa_number_sid",
            "provider",
        }
        assert expected <= columns
        row = connection.execute(
            text("SELECT number_source, provider FROM voice_channel_configs WHERE id='cfg-1'")
        ).one()
        assert row == ("bring_own", "twilio")
        assert inspect(connection).has_table("voice_call_turns")

        # An operator may already have applied a column manually; do not add it twice.
        with Operations.context(MigrationContext.configure(connection)):
            _MIGRATION._add_column_if_missing(
                "voice_channel_configs", Column("provider", String(length=30))
            )
            _MIGRATION.downgrade()

        assert not inspect(connection).has_table("voice_call_turns")
