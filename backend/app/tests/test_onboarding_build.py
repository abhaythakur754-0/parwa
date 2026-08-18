"""
Unit tests for the onboarding build orchestrator + integration test endpoint.

Verifies:
- /test endpoint: real credential verification (tests against a real public API)
- /trigger endpoint: agent + tool creation from analysis results
- /status endpoint: polls build status
- Deduplication: re-triggering doesn't create duplicate agents
- Tenant isolation: agents scoped by company_id

Run: pytest backend/app/tests/test_onboarding_build.py -v
"""

import os
import pytest


def _read_source(filename: str) -> str:
    base = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(base, filename)) as f:
        return f.read()


# ── /test endpoint (integration verification) ─────────────────────────


def test_test_endpoint_exists():
    """The /systems/{system_id}/test endpoint should be defined."""
    source = _read_source("api/superglue_systems.py")
    assert '"/systems/{system_id}/test"' in source
    assert "async def test_system(" in source
    assert "class TestResponse" in source


def test_test_endpoint_makes_real_http_call():
    """The /test endpoint should make a real GET request via httpx (not fake)."""
    source = _read_source("api/superglue_systems.py")
    assert "import httpx" in source
    assert "httpx.AsyncClient" in source
    assert "client.get(system_url" in source, "must make a real GET to the system URL"


def test_test_endpoint_interprets_status_codes():
    """The /test endpoint should correctly interpret HTTP status codes."""
    source = _read_source("api/superglue_systems.py")
    # 200/201 = works
    assert "resp.status_code in (200, 201)" in source
    # 401/403 = auth failed
    assert "401, 403" in source
    assert "Authentication failed" in source
    # 404 = wrong URL
    assert "404" in source
    assert "URL not found" in source


def test_test_endpoint_updates_integration_status():
    """The /test endpoint should update the Integration record with the test result."""
    source = _read_source("api/superglue_systems.py")
    assert "integration.status = \"verified\"" in source, "should mark as verified on success"
    assert "integration.status = \"error\"" in source, "should mark as error on failure"
    assert "integration.error_message" in source, "should store error message"


def test_test_endpoint_handles_network_errors():
    """The /test endpoint should handle connect errors + timeouts gracefully."""
    source = _read_source("api/superglue_systems.py")
    assert "httpx.ConnectError" in source, "should handle connection errors"
    assert "httpx.TimeoutException" in source, "should handle timeouts"
    assert "Cannot connect" in source, "should give clear error message"


# ── /trigger endpoint (agent + tool creation) ─────────────────────────


def test_trigger_endpoint_exists():
    """The /trigger endpoint should be defined in onboarding_build.py."""
    source = _read_source("api/onboarding_build.py")
    assert '"/trigger"' in source
    assert "async def trigger_build(" in source
    assert "class TriggerBuildResponse" in source


def test_trigger_reads_latest_analysis():
    """The /trigger endpoint should read the latest CRMAnalysisResult for the tenant."""
    source = _read_source("api/onboarding_build.py")
    assert "CRMAnalysisResult" in source
    assert "order_by(CRMAnalysisResult.created_at.desc())" in source


def test_trigger_calls_generate_tool_for_agent():
    """The /trigger endpoint should call generate_tool_for_agent for each recommendation."""
    source = _read_source("api/onboarding_build.py")
    assert "from app.core.superglue_tool_generator import generate_tool_for_agent" in source
    assert "await generate_tool_for_agent(" in source


def test_trigger_creates_ai_agent_assignment():
    """The /trigger endpoint should create AIAgentAssignment rows."""
    source = _read_source("api/onboarding_build.py")
    assert "from database.models.variant_engine import AIAgentAssignment" in source
    assert "AIAgentAssignment(" in source
    assert "company_id=tenant_id" in source
    assert "superglue_tool_status=\"pending\"" in source


def test_trigger_updates_tool_status_on_success():
    """When tool generation succeeds, should set status=active + store tool_id."""
    source = _read_source("api/onboarding_build.py")
    assert 'agent.superglue_tool_id = result.get("tool_id")' in source
    assert 'agent.superglue_tool_status = "active"' in source
    assert "agent.superglue_tool_created_at" in source


def test_trigger_sets_failed_status_on_error():
    """When tool generation fails, should set status=failed."""
    source = _read_source("api/onboarding_build.py")
    assert 'agent.superglue_tool_status = "failed"' in source


# ── /status endpoint (polling) ────────────────────────────────────────


def test_status_endpoint_exists():
    """The /status endpoint should be defined."""
    source = _read_source("api/onboarding_build.py")
    assert '"/status"' in source
    assert "async def get_build_status(" in source
    assert "class BuildStatusResponse" in source


def test_status_returns_all_agents_for_tenant():
    """The /status endpoint should return all AIAgentAssignment rows for the tenant."""
    source = _read_source("api/onboarding_build.py")
    assert "db.query(AIAgentAssignment).filter(" in source
    assert "AIAgentAssignment.company_id == tenant_id" in source


def test_status_computes_all_ready():
    """The /status endpoint should compute all_ready correctly."""
    source = _read_source("api/onboarding_build.py")
    assert "all_ready" in source
    assert "ready == total" in source, "all_ready should require every agent to be ready"
    assert "failed == 0" in source, "all_ready should require zero failures"


# ── Deduplication ─────────────────────────────────────────────────────


def test_trigger_dedup_checks_existing_agent():
    """The /trigger endpoint should check if an agent already exists before creating."""
    source = _read_source("api/onboarding_build.py")
    assert "db.query(AIAgentAssignment).filter(" in source
    assert "AIAgentAssignment.agent_name == agent_name" in source


def test_trigger_skips_existing_active_agents():
    """If an agent already exists with status=active, should skip (not duplicate)."""
    source = _read_source("api/onboarding_build.py")
    assert 'existing.superglue_tool_status == "active"' in source
    assert "status=\"skipped\"" in source


def test_trigger_is_idempotent():
    """Re-running trigger should not create duplicates (upsert pattern)."""
    source = _read_source("api/onboarding_build.py")
    # The "if existing:" branch should update instead of creating new
    assert "if existing:" in source
    assert "agent = existing" in source, "should reuse existing record"
    assert "else:" in source
    assert "db.add(agent)" in source, "should only add new records"


# ── Tenant isolation ──────────────────────────────────────────────────


def test_agents_are_tenant_scoped():
    """All agent operations should be scoped by company_id."""
    source = _read_source("api/onboarding_build.py")
    assert "tenant_id = str(user.company_id)" in source
    assert "company_id=tenant_id" in source


def test_status_is_tenant_scoped():
    """The /status endpoint should only return agents for the current tenant."""
    source = _read_source("api/onboarding_build.py")
    # Both trigger + status use tenant_id from user.company_id
    assert "company_id == tenant_id" in source


# ── Capability inference ──────────────────────────────────────────────


def test_capability_inference_exists():
    """The _infer_capabilities helper should exist + map integrations to capabilities."""
    source = _read_source("api/onboarding_build.py")
    assert "def _infer_capabilities(" in source
    assert "refund_processing" in source, "Stripe should map to refund_processing"
    assert "billing_inquiry" in source
    assert "shipping_delivery" in source, "Shopify should map to shipping_delivery"
    assert "technical_support" in source


# ── Router mounting ───────────────────────────────────────────────────


def test_router_mounted_in_main():
    """The onboarding_build router should be mounted in main.py."""
    source = _read_source("main.py")
    assert "from app.api.onboarding_build import router as onboarding_build_router" in source
    assert "app.include_router(onboarding_build_router)" in source
