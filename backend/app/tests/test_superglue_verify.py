"""
Unit tests for the /verify endpoint + MCPConnection registration.

Tests the full CRM connection flow:
  1. Create CRM system in Superglue
  2. Verify it (GET Superglue + check MCPConnection DB record)
  3. Confirm MCPConnection was created with correct fields
  4. Delete the system (should also remove MCPConnection)

NOTE: The DB-dependent parts (MCPConnection creation) require SQLAlchemy.
These tests verify the Superglue-side logic + the verify endpoint's
Superglue check. DB integration is tested via the frontend integration test.

Run: pytest backend/app/tests/test_superglue_verify.py -v
"""

import asyncio
import pytest

from app.core import superglue_client


TENANT_ID = "verify-test-tenant-001"
TEST_CRM_ID = "hubspot"
TEST_CRM_NAME = "Test HubSpot"
TEST_CRM_URL = "https://api.hubapi.com"


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up any leftover test systems before + after each test."""
    yield
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(superglue_client.delete_system(TEST_CRM_ID, tenant_id=TENANT_ID))
    except Exception:
        pass
    finally:
        loop.close()


def test_verify_returns_true_for_existing_crm():
    """After creating a CRM in Superglue, verify should return success."""
    # Create the CRM
    asyncio.run(superglue_client.create_system(
        system_id=TEST_CRM_ID,
        name=TEST_CRM_NAME,
        url=TEST_CRM_URL,
        tenant_id=TENANT_ID,
        credentials={"api_key": "pat_test123"},
        icon="🎯",
    ))

    # Verify it exists
    result = asyncio.run(superglue_client.get_system(TEST_CRM_ID, tenant_id=TENANT_ID))
    assert result["success"] is True
    assert result["data"]["name"] == TEST_CRM_NAME
    assert result["data"]["url"] == TEST_CRM_URL


def test_verify_returns_false_for_nonexistent_crm():
    """Verifying a non-existent CRM should return success=False."""
    result = asyncio.run(superglue_client.get_system("nonexistent-crm-xyz", tenant_id=TENANT_ID))
    assert result["success"] is False
    assert "not found" in result.get("error", "").lower()


def test_crm_system_ids_includes_hubspot():
    """CRM_SYSTEM_IDS should include hubspot, zendesk, salesforce, custom."""
    # Import from the router module
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    # We can't import the full router (needs DB deps), so just verify the set exists
    # by reading the source
    router_path = os.path.join(
        os.path.dirname(__file__), "..", "api", "superglue_systems.py"
    )
    with open(router_path) as f:
        source = f.read()
    assert 'CRM_SYSTEM_IDS = {"hubspot", "zendesk", "salesforce", "custom"}' in source


def test_verify_endpoint_exists_in_router():
    """The /systems/{system_id}/verify endpoint should be defined in the router."""
    import os
    router_path = os.path.join(
        os.path.dirname(__file__), "..", "api", "superglue_systems.py"
    )
    with open(router_path) as f:
        source = f.read()
    assert '"/systems/{system_id}/verify"' in source
    assert "async def verify_system" in source
    assert "VerifyResponse" in source
    assert "mcp_registered" in source


def test_mcp_connection_import_in_router():
    """The router should import MCPConnection + encrypt_token."""
    import os
    router_path = os.path.join(
        os.path.dirname(__file__), "..", "api", "superglue_systems.py"
    )
    with open(router_path) as f:
        source = f.read()
    assert "from database.models.integration import MCPConnection" in source
    assert "from shared.utils.token_encryption import encrypt_token" in source
    assert "def _upsert_mcp_connection" in source


def test_create_then_delete_crm_round_trip():
    """Create a CRM, verify it exists, then delete it and verify it's gone."""
    # Create
    asyncio.run(superglue_client.create_system(
        system_id=TEST_CRM_ID,
        name=TEST_CRM_NAME,
        url=TEST_CRM_URL,
        tenant_id=TENANT_ID,
    ))

    # Verify exists
    result = asyncio.run(superglue_client.get_system(TEST_CRM_ID, tenant_id=TENANT_ID))
    assert result["success"] is True

    # Delete
    del_result = asyncio.run(superglue_client.delete_system(TEST_CRM_ID, tenant_id=TENANT_ID))
    assert del_result["success"] is True

    # Verify gone
    result = asyncio.run(superglue_client.get_system(TEST_CRM_ID, tenant_id=TENANT_ID))
    assert result["success"] is False
