"""Tests for tenant-isolated Superglue service-account storage."""

from types import SimpleNamespace

from sqlalchemy import UniqueConstraint

from app.core.superglue_tenant_accounts import _set_tenant_context
from database.models.integration import SuperglueTenantAccount


class _FakeDB:
    def __init__(self, dialect):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect))
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))


def test_service_account_model_is_unique_per_company_and_encrypted():
    assert SuperglueTenantAccount.__tablename__ == "superglue_tenant_accounts"
    assert any(
        isinstance(constraint, UniqueConstraint)
        and list(constraint.columns.keys()) == ["company_id"]
        for constraint in SuperglueTenantAccount.__table__.constraints
    )
    assert SuperglueTenantAccount.api_key_encrypted.nullable is False
    assert SuperglueTenantAccount.service_account_id.unique is True


def test_tenant_context_is_set_for_rls_protected_key_lookup():
    db = _FakeDB("postgresql")
    _set_tenant_context(db, "tenant-123")

    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "app.current_tenant_id" in sql
    assert params == {"tenant_id": "tenant-123"}


def test_sqlite_does_not_execute_postgres_rls_context_statement():
    db = _FakeDB("sqlite")
    _set_tenant_context(db, "tenant-123")
    assert db.calls == []


def test_superglue_call_queue_payload_encryption_round_trips():
    import importlib.util
    import json
    from pathlib import Path

    # backend/tests/conftest.py stubs shared.utils.token_encryption for most
    # tests. Load the actual source module here so this security contract
    # exercises Fernet rather than the "encrypted-mock" fixture.
    module_path = (
        Path(__file__).resolve().parents[2]
        / "shared"
        / "utils"
        / "token_encryption.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_parwa_real_token_encryption", module_path
    )
    assert spec is not None and spec.loader is not None
    token_encryption = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(token_encryption)

    payload = {"customer_email": "customer@example.com", "ticket_id": "ticket-123"}
    serialized = json.dumps(payload)
    encrypted = token_encryption.encrypt_token(serialized)
    assert encrypted
    assert encrypted != serialized
    assert json.loads(token_encryption.decrypt_token(encrypted)) == payload
