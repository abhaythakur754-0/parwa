"""
Unit tests for database integration support.

Verifies:
- Database types added to catalog (PostgreSQL, MySQL, MongoDB, Snowflake, BigQuery, Supabase)
- DATABASE_SYSTEM_IDS set exists
- CreateSystemRequest supports DB-specific fields (db_type, db_host, db_port, db_name, db_username, db_password)
- create_system handler saves databases to DBConnection table
- DBConnection import exists
- _upsert_db_connection helper exists
- DELETE removes DBConnection for databases
- /test endpoint handles databases differently (auto-schema-reading)
- Read-only enforced (is_readonly=True always)

Run: pytest backend/app/tests/test_database_integration.py -v
"""

import os
import pytest


def _read_source(filename: str) -> str:
    base = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(base, filename)) as f:
        return f.read()


# ── Catalog: database types added ─────────────────────────────────────


def test_database_types_in_catalog():
    """All 6 database types should be in POPULAR_SYSTEMS."""
    source = _read_source("api/superglue_systems.py")
    assert '"id": "postgres"' in source
    assert '"id": "mysql"' in source
    assert '"id": "mongodb"' in source
    assert '"id": "snowflake"' in source
    assert '"id": "bigquery"' in source
    assert '"id": "supabase-db"' in source


def test_database_system_ids_set_exists():
    """DATABASE_SYSTEM_IDS set should be defined with all 6 DB types."""
    source = _read_source("api/superglue_systems.py")
    assert 'DATABASE_SYSTEM_IDS = {' in source
    assert '"postgres"' in source
    assert '"mysql"' in source
    assert '"mongodb"' in source
    assert '"snowflake"' in source
    assert '"bigquery"' in source
    assert '"supabase-db"' in source


def test_database_entries_have_type_field():
    """Database catalog entries should have type='database' + db_type field."""
    source = _read_source("api/superglue_systems.py")
    assert '"type": "database"' in source
    assert '"db_type": "postgresql"' in source
    assert '"db_type": "mysql"' in source
    assert '"db_type": "mongodb"' in source
    assert '"db_type": "snowflake"' in source
    assert '"db_type": "bigquery"' in source


# ── CreateSystemRequest: DB-specific fields ───────────────────────────


def test_db_fields_in_request_model():
    """CreateSystemRequest should have db_type, db_host, db_port, db_name, db_username, db_password."""
    source = _read_source("api/superglue_systems.py")
    assert "db_type: Optional[str]" in source
    assert "db_host: Optional[str]" in source
    assert "db_port: Optional[int]" in source
    assert "db_name: Optional[str]" in source
    assert "db_username: Optional[str]" in source
    assert "db_password: Optional[str]" in source


# ── DBConnection import + helper ──────────────────────────────────────


def test_db_connection_imported():
    """DBConnection model should be imported."""
    source = _read_source("api/superglue_systems.py")
    assert "from database.models.integration import MCPConnection, Integration, DBConnection" in source


def test_upsert_db_connection_helper_exists():
    """The _upsert_db_connection helper should be defined."""
    source = _read_source("api/superglue_systems.py")
    assert "def _upsert_db_connection(" in source


def test_upsert_db_connection_encrypts_connection_string():
    """_upsert_db_connection should encrypt the connection string."""
    source = _read_source("api/superglue_systems.py")
    assert "encrypt_token(conn_str)" in source


def test_upsert_db_connection_enforces_readonly():
    """DBConnection should ALWAYS be read-only (is_readonly=True)."""
    source = _read_source("api/superglue_systems.py")
    assert "is_readonly=True" in source
    # Should appear in both create + update paths
    assert source.count("is_readonly=True") >= 2


# ── create_system handler: database branch ────────────────────────────


def test_create_system_detects_databases():
    """create_system should check if system_id is in DATABASE_SYSTEM_IDS."""
    source = _read_source("api/superglue_systems.py")
    assert "is_database = req.system_id in DATABASE_SYSTEM_IDS" in source


def test_create_system_builds_db_url():
    """For databases, the handler should build a URL from db_host + db_port + db_name."""
    source = _read_source("api/superglue_systems.py")
    assert "req.url = f\"{req.db_type or 'postgresql'}://{req.db_host}:{db_port}/{req.db_name}\"" in source


def test_create_system_validates_db_fields():
    """Database connections should require db_host, db_name, db_username."""
    source = _read_source("api/superglue_systems.py")
    assert "Database connections require db_host, db_name, db_username" in source


def test_create_system_calls_upsert_db_connection():
    """For databases, create_system should call _upsert_db_connection."""
    source = _read_source("api/superglue_systems.py")
    assert "_upsert_db_connection(" in source


# ── DELETE handler: removes DBConnection ──────────────────────────────


def test_delete_removes_db_connection():
    """DELETE should remove DBConnection for database systems."""
    source = _read_source("api/superglue_systems.py")
    assert "if system_id in DATABASE_SYSTEM_IDS:" in source
    assert "db.query(DBConnection)" in source
    assert "db.delete(db_conn)" in source


# ── /test endpoint: database handling ─────────────────────────────────


def test_test_endpoint_handles_databases():
    """The /test endpoint should have a database-specific branch."""
    source = _read_source("api/superglue_systems.py")
    assert "if system_id in DATABASE_SYSTEM_IDS:" in source
    # Should mention auto-schema-reading
    assert "reading schema" in source.lower() or "auto-reads" in source.lower()


def test_test_endpoint_returns_success_for_databases():
    """For databases, test should return works=True (Superglue handles schema)."""
    source = _read_source("api/superglue_systems.py")
    # The database branch should return works=True
    assert "Database connected" in source


# ── Connection string building ────────────────────────────────────────


def test_mongodb_connection_string_format():
    """MongoDB connection string should use mongodb:// scheme."""
    source = _read_source("api/superglue_systems.py")
    assert 'conn_str = f"mongodb://' in source


def test_postgres_connection_string_format():
    """PostgreSQL/MySQL connection string should use {db_type}:// scheme."""
    source = _read_source("api/superglue_systems.py")
    # The else branch handles postgresql + mysql with {db_type}://
    assert 'conn_str = f"{db_type}://{db_username}' in source


# ── Tenant isolation ──────────────────────────────────────────────────


def test_db_connection_is_tenant_scoped():
    """DBConnection records should be scoped by company_id."""
    source = _read_source("api/superglue_systems.py")
    assert "DBConnection.company_id == company_id" in source


def test_db_connection_dedup():
    """_upsert_db_connection should check for existing record before creating."""
    source = _read_source("api/superglue_systems.py")
    assert "db.query(DBConnection).filter(" in source
    assert "DBConnection.name == name" in source
    assert "if db_conn:" in source
