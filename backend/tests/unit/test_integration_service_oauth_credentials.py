"""IntegrationService must not expose OAuth tokens from local metadata."""

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
    def __init__(self, row):
        self.row = row

    def query(self, model):
        return _Query(self.row)


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
