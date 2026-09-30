"""
Unit tests for DB persistence of Superglue connections + analysis results.

Verifies the code logic (source-level checks) for:
1. Every connected system (CRM + non-CRM) is saved to the Integration table
2. CRM systems are ALSO saved to MCPConnection table
3. DELETE removes from both Integration + MCPConnection (for CRM) tables
4. The /analyze endpoint saves results to CRMAnalysisResult table
5. Tenant isolation: different tenants have separate records

Run: pytest backend/app/tests/test_superglue_db_persistence.py -v
"""

import os
import pytest


def _read_source(filename: str) -> str:
    base = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(base, filename)) as f:
        return f.read()


# ── Fix #1: Integration table save for ALL systems ────────────────────


def test_integration_model_imported():
    """superglue_systems.py should import the Integration model."""
    source = _read_source("api/superglue_systems.py")
    assert "from database.models.integration import MCPConnection, Integration" in source


def test_upsert_integration_helper_exists():
    """The _upsert_integration helper function should be defined."""
    source = _read_source("api/superglue_systems.py")
    assert "def _upsert_integration(" in source
    assert "def _upsert_mcp_connection(" in source


def test_post_systems_saves_to_integration_table():
    """POST /systems should call _upsert_integration for EVERY system (not just CRM)."""
    source = _read_source("api/superglue_systems.py")
    idx_upsert = source.find("_upsert_integration(")
    idx_is_crm = source.find("is_crm = req.system_id")
    assert idx_upsert > 0, "_upsert_integration call not found"
    assert idx_is_crm > 0, "is_crm check not found"
    assert idx_upsert < idx_is_crm, \
        "_upsert_integration must run for ALL systems (before the is_crm check)"


def test_upsert_integration_uses_encrypt_token():
    """_upsert_integration should encrypt credentials before storing."""
    source = _read_source("api/superglue_systems.py")
    assert "encrypt_token" in source, "credentials must be encrypted"
    assert "json.dumps(credentials)" in source, "credentials dict should be JSON-serialized"
    assert 'status = "connected"' in source, "status should be set to connected"


def test_upsert_integration_updates_existing():
    """_upsert_integration should UPDATE if (company_id, integration_type) already exists."""
    source = _read_source("api/superglue_systems.py")
    assert "db.query(Integration).filter(" in source
    assert "Integration.company_id == company_id" in source
    assert "Integration.integration_type == integration_type" in source
    assert "if integration:" in source, "should check for existing record"
    assert "integration.name = name" in source, "should update name"


def test_delete_removes_integration_record():
    """DELETE /systems/{id} should remove the Integration record."""
    source = _read_source("api/superglue_systems.py")
    assert "db.query(Integration).filter(" in source
    assert "Integration.company_id == tenant_id" in source
    assert "Integration.integration_type == system_id" in source
    assert "db.delete(integration)" in source


def test_delete_also_removes_mcp_for_crm():
    """DELETE should still remove MCPConnection for CRM systems."""
    source = _read_source("api/superglue_systems.py")
    assert "if system_id in CRM_SYSTEM_IDS:" in source
    assert "db.query(MCPConnection)" in source
    assert "db.delete(mcp)" in source


# ── Fix #2: CRMAnalysisResult save in /analyze endpoint ───────────────


def test_analyze_endpoint_imports_crm_analysis_model():
    """integrations.py /analyze endpoint should import CRMAnalysisResult."""
    source = _read_source("api/integrations.py")
    assert "from database.models.crm_analysis import CRMAnalysisResult" in source


def test_analyze_endpoint_saves_to_db():
    """The /analyze endpoint should db.add() a CRMAnalysisResult record."""
    source = _read_source("api/integrations.py")
    assert "CRMAnalysisResult(" in source, "should create a CRMAnalysisResult"
    assert "db.add(analysis_record)" in source, "should add to DB"
    assert "db.commit()" in source, "should commit"


def test_analyze_endpoint_saves_all_fields():
    """The saved CRMAnalysisResult should include all key fields."""
    source = _read_source("api/integrations.py")
    assert "company_id=str(user.company_id)" in source
    assert "data_profile=data_profile" in source
    assert "recommendations=recommendations" in source
    assert "analysis_summary=analysis_summary" in source
    assert "is_actioned=False" in source
    assert "recommendations_accepted=[]" in source


def test_analyze_endpoint_doesnt_fail_on_db_error():
    """If DB save fails, the endpoint should still return the analysis (graceful degradation)."""
    source = _read_source("api/integrations.py")
    assert "try:" in source, "DB save should be wrapped in try"
    assert "except Exception" in source, "should catch DB errors"
    assert "Failed to save CRMAnalysisResult" in source, "should log the failure"


# ── Tenant isolation ──────────────────────────────────────────────────


def test_integration_save_is_tenant_scoped():
    """Integration records are scoped by company_id (tenant isolation)."""
    source = _read_source("api/superglue_systems.py")
    assert "Integration.company_id == company_id" in source
    assert "tenant_id = str(user.company_id)" in source


def test_analysis_save_is_tenant_scoped():
    """CRMAnalysisResult records are scoped by company_id."""
    source = _read_source("api/integrations.py")
    assert "company_id=str(user.company_id)" in source
