"""Keep the Render blueprint aligned with production integration requirements."""

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def _service_env(service):
    return {
        item["key"]: item
        for item in service.get("envVars", [])
        if isinstance(item, dict) and item.get("key")
    }


def test_render_backend_declares_required_production_credentials():
    render = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {service["name"]: service for service in render["services"]}
    backend = _service_env(services["parwa-backend"])

    required = {
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATA_ENCRYPTION_KEY",
        "PRICING_SIGNING_KEY",
        "REFRESH_TOKEN_PEPPER",
        "MCP_AUTH_TOKEN",
        "MCP_SERVER_URL",
        "BUILDER_API_URL",
        "BUILDER_API_KEY",
        "CRM_ANALYSER_URL",
        "CRM_ANALYSER_API_KEY",
        "SUPERGLUE_API_URL",
        "SUPERGLUE_AUTH_TOKEN",
        "SUPERGLUE_LLM_API_KEY",
        "RAZORPAY_KEY_ID",
        "RAZORPAY_KEY_SECRET",
        "RAZORPAY_WEBHOOK_SECRET",
        "GOOGLE_CLIENT_SECRET",
        "BREVO_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
    }
    assert required <= set(backend), f"Missing Render backend env declarations: {sorted(required - set(backend))}"

    for key in required:
        assert backend[key].get("sync") is False, f"{key} must be a manually managed secret"


def test_render_worker_declares_worker_side_secrets():
    render = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {service["name"]: service for service in render["services"]}
    worker = _service_env(services["parwa-worker"])

    required = {
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATA_ENCRYPTION_KEY",
        "PRICING_SIGNING_KEY",
        "REFRESH_TOKEN_PEPPER",
        "MCP_AUTH_TOKEN",
        "MCP_SERVER_URL",
        "BREVO_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
    }
    assert required <= set(worker), f"Missing Render worker env declarations: {sorted(required - set(worker))}"


def test_env_example_documents_environment_only_external_credentials():
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for key in (
        "MCP_AUTH_TOKEN",
        "BUILDER_API_KEY",
        "SUPERGLUE_API_URL",
        "SUPERGLUE_AUTH_TOKEN",
        "SUPERGLUE_LLM_API_KEY",
        "SUPERGLUE_SESSION_ID",
    ):
        assert f"{key}=" in env_example



def test_production_env_template_documents_external_agent_endpoints():
    env = (REPO_ROOT / ".env.prod.example").read_text(encoding="utf-8")
    for key in (
        "BUILDER_API_URL",
        "BUILDER_API_KEY",
        "CRM_ANALYSER_URL",
        "CRM_ANALYSER_API_KEY",
        "SUPERGLUE_API_URL",
        "SUPERGLUE_AUTH_TOKEN",
        "SUPERGLUE_LLM_API_KEY",
    ):
        assert f"{key}=" in env
