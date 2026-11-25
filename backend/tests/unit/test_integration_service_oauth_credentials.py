"""IntegrationService credential encryption, migration, and OAuth isolation tests."""

import json
from types import SimpleNamespace

from app.services.integration_service import IntegrationService


class _Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.row


class _DB:
    def __init__(self, row=None):
        self.row = row
        self.flush_count = 0
        self.execute_count = 0
        self.commit_count = 0
        self.added = None

    def query(self, model):
        return _Query(self.row)

    def flush(self):
        self.flush_count += 1

    def add(self, value):
        self.added = value

    def execute(self, statement):
        self.execute_count += 1
        return None

    def commit(self):
        self.commit_count += 1
        return None


def test_oauth_integrations_do_not_return_local_metadata_as_credentials():
    row = SimpleNamespace(
        company_id="tenant-1",
        integration_type="hubspot",
        status="verified",
        settings={"auth_type": "oauth"},
        credentials_encrypted="encrypted-empty-object",
    )
    service = IntegrationService(_DB(row))

    assert service.get_credential_config("tenant-1", "hubspot") is None



def test_legacy_plaintext_credentials_are_reencrypted_on_read(monkeypatch):
    row = SimpleNamespace(
        credentials_encrypted=json.dumps({"api_key": "legacy-secret"}),
    )
    db = _DB(row)
    service = IntegrationService(db)
    encrypted_values = []
    monkeypatch.setattr(
        "app.services.integration_service.encrypt_token",
        lambda value: encrypted_values.append(value) or "fernet:opaque-ciphertext",
    )

    assert service._load_credentials(row) == {"api_key": "legacy-secret"}
    assert row.credentials_encrypted == "fernet:opaque-ciphertext"
    assert encrypted_values == [json.dumps({"api_key": "legacy-secret"})]
    assert db.flush_count == 1


def test_existing_encrypted_credentials_are_not_reencrypted(monkeypatch):
    row = SimpleNamespace(credentials_encrypted="already-encrypted")
    db = _DB(row)
    service = IntegrationService(db)
    monkeypatch.setattr(
        IntegrationService,
        "_parse_json",
        staticmethod(lambda value: {"api_key": "secret"}),
    )

    def unexpected_encrypt(value):
        raise AssertionError("encrypted credentials must not be encrypted again")

    monkeypatch.setattr("app.services.integration_service.encrypt_token", unexpected_encrypt)
    assert service._load_credentials(row) == {"api_key": "secret"}
    assert row.credentials_encrypted == "already-encrypted"
    assert db.flush_count == 0


def test_skipping_validation_keeps_integration_pending(monkeypatch):
    from app.services import integration_service as service_module

    db = _DB()
    service = IntegrationService(db)
    monkeypatch.setattr(
        service_module,
        "get_integration_by_key",
        lambda key: SimpleNamespace(auth_schema=SimpleNamespace(fields=[])),
    )
    monkeypatch.setattr(service_module, "encrypt_token", lambda value: "fernet:opaque-ciphertext")
    monkeypatch.setattr(
        IntegrationService,
        "_to_dict",
        lambda self, integration, mask_credentials=False: {"status": integration.status},
    )

    result = service.create_integration(
        company_id="tenant-1",
        integration_type="hubspot",
        name="HubSpot",
        config={"api_key": "secret"},
        validate=False,
    )

    assert result["status"] == "pending"
    assert db.added.credentials_encrypted == "fernet:opaque-ciphertext"
    assert db.execute_count == 0
    assert db.commit_count == 0



def test_unverified_integration_does_not_trigger_escalation_auto_retry():
    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/integrations.py").read_text(encoding="utf-8")
    assert 'if integration.get("status") in {"active", "verified"}:' in source
