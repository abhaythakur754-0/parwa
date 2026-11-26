"""External service credentials must never be embedded in source defaults."""

import importlib
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
for _path in (str(_REPO_ROOT), str(_SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def test_backend_client_fails_closed_without_environment_credentials(monkeypatch):
    monkeypatch.delenv("SUPERGLUE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SUPERGLUE_LLM_API_KEY", raising=False)

    from app.core import superglue_client

    client = importlib.reload(superglue_client)
    assert client._get_config()[1] == ""
    assert client._get_llm_key() == ""
    assert client.is_configured() is False


def test_tool_factory_refuses_requests_without_environment_token(monkeypatch):
    monkeypatch.delenv("SUPERGLUE_AUTH_TOKEN", raising=False)

    import tool_factory

    factory = importlib.reload(tool_factory)
    assert factory.SUPERGLUE_TOKEN == ""
    with pytest.raises(RuntimeError, match="SUPERGLUE_AUTH_TOKEN is required"):
        factory.api_request("GET", "/v1/tools")


def test_self_extension_llm_key_has_no_source_fallback(monkeypatch):
    monkeypatch.delenv("SUPERGLUE_LLM_API_KEY", raising=False)

    import self_extension_loop

    loop = importlib.reload(self_extension_loop)
    assert loop.LLM_KEY == ""


def test_remote_builder_requires_environment_api_key(monkeypatch):
    monkeypatch.delenv("BUILDER_API_KEY", raising=False)

    from app.core import remote_builder_client

    builder = importlib.reload(remote_builder_client)
    with pytest.raises(RuntimeError, match="BUILDER_API_KEY is required"):
        builder._builder_headers()

    monkeypatch.setenv("BUILDER_API_KEY", "test-builder-key")
    builder = importlib.reload(remote_builder_client)
    assert builder._builder_headers()["X-API-Key"] == "test-builder-key"


def test_production_e2e_script_reads_builder_key_from_environment(monkeypatch):
    monkeypatch.delenv("BUILDER_API_KEY", raising=False)

    import production_e2e_test

    script = importlib.reload(production_e2e_test)
    assert script.BUILDER_KEY == ""



def test_production_e2e_uses_explicit_authenticated_endpoints_and_mutation_opt_in(monkeypatch):
    monkeypatch.setenv("BUILDER_API_URL", "https://builder.sandbox.example")
    monkeypatch.setenv("BUILDER_API_KEY", "test-builder-key")
    monkeypatch.setenv("CRM_ANALYSER_URL", "https://crm.sandbox.example")
    monkeypatch.setenv("CRM_ANALYSER_API_KEY", "test-crm-key")
    monkeypatch.setenv("PARWA_E2E_ALLOW_MUTATIONS", "true")

    import production_e2e_test

    script = importlib.reload(production_e2e_test)
    assert script.BUILDER_URL == "https://builder.sandbox.example"
    assert script.BUILDER_KEY == "test-builder-key"
    assert script.CRM_URL == "https://crm.sandbox.example"
    assert script.CRM_ANALYSER_API_KEY == "test-crm-key"
    assert script.ALLOW_MUTATIONS is True
    source = (_SCRIPTS_DIR / "production_e2e_test.py").read_text(encoding="utf-8")
    assert "preview-chat-" not in source
    assert 'headers={"Authorization": f"Bearer {CRM_ANALYSER_API_KEY}"}' in source



def test_production_e2e_read_only_health_phase_does_not_require_mutation_opt_in(monkeypatch):
    import production_e2e_test

    script = importlib.reload(production_e2e_test)
    monkeypatch.setattr(script, "ALLOW_MUTATIONS", False)
    monkeypatch.setattr(script, "PHASES", [lambda: True])
    monkeypatch.setattr(sys, "argv", ["production_e2e_test.py", "--phase", "0"])

    with pytest.raises(SystemExit) as result:
        script.main()
    assert result.value.code == 0


def test_production_e2e_mutating_phases_require_explicit_opt_in(monkeypatch):
    import production_e2e_test

    script = importlib.reload(production_e2e_test)
    monkeypatch.setattr(script, "ALLOW_MUTATIONS", False)
    monkeypatch.setattr(sys, "argv", ["production_e2e_test.py", "--phase", "1"])

    with pytest.raises(SystemExit, match="Refusing to mutate external test tenants"):
        script.main()
