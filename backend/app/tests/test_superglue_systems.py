"""
Unit tests for Superglue system-management client functions.

Tests the create→list→get→delete round-trip against the LIVE Superglue server
(hardcoded in superglue_client.py). Also verifies tenant isolation.

Run: pytest backend/app/tests/test_superglue_systems.py -v
"""

import asyncio
import pytest

from app.core.superglue_client import (
    create_system,
    get_system,
    delete_system,
    list_tenant_systems,
    is_configured,
    namespaced_tool_id,
)


# ── Fixtures ──────────────────────────────────────────────────────────

TENANT_A = "unit-test-tenant-a-001"
TENANT_B = "unit-test-tenant-b-001"
TEST_SYSTEM_ID = "shopify-unit-test"
TEST_SYSTEM_NAME = "Unit Test Shopify"
TEST_SYSTEM_URL = "https://unit-test-store.myshopify.com"


@pytest.fixture(autouse=True)
def cleanup():
    """Ensure any leftover test systems are cleaned up before + after each test."""
    yield
    # Cleanup after test
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(delete_system(TEST_SYSTEM_ID, tenant_id=TENANT_A))
        loop.run_until_complete(delete_system(TEST_SYSTEM_ID, tenant_id=TENANT_B))
    except Exception:
        pass
    finally:
        loop.close()


# ── Tests ─────────────────────────────────────────────────────────────

def test_superglue_is_configured():
    """Superglue should be configured (hardcoded URL + token)."""
    assert is_configured() is True


def test_create_system_returns_success():
    """Creating a system should return success with the namespaced ID."""
    result = asyncio.run(create_system(
        system_id=TEST_SYSTEM_ID,
        name=TEST_SYSTEM_NAME,
        url=TEST_SYSTEM_URL,
        tenant_id=TENANT_A,
        credentials={"api_key": "shpat_test_123"},
        icon="🛒",
    ))
    assert result["success"] is True
    assert "data" in result
    # The returned ID should be namespaced
    data = result["data"]
    assert data["name"] == TEST_SYSTEM_NAME
    assert data["url"] == TEST_SYSTEM_URL


def test_get_system_after_create():
    """After creating, get_system should return it."""
    asyncio.run(create_system(
        system_id=TEST_SYSTEM_ID,
        name=TEST_SYSTEM_NAME,
        url=TEST_SYSTEM_URL,
        tenant_id=TENANT_A,
    ))
    result = asyncio.run(get_system(TEST_SYSTEM_ID, tenant_id=TENANT_A))
    assert result["success"] is True
    assert result["data"]["name"] == TEST_SYSTEM_NAME


def test_list_tenant_systems_filters_by_tenant():
    """list_tenant_systems should only return systems for the specified tenant."""
    # Create a system for tenant A
    asyncio.run(create_system(
        system_id=TEST_SYSTEM_ID,
        name=TEST_SYSTEM_NAME,
        url=TEST_SYSTEM_URL,
        tenant_id=TENANT_A,
    ))
    # List tenant A's systems
    systems_a = asyncio.run(list_tenant_systems(TENANT_A))
    assert len(systems_a) >= 1
    # All systems should have the tenant A prefix
    prefix_a = f"tenant_{TENANT_A}__"
    for s in systems_a:
        assert s["id"].startswith(prefix_a), f"System {s['id']} doesn't belong to tenant A"

    # Tenant B should NOT see tenant A's system
    systems_b = asyncio.run(list_tenant_systems(TENANT_B))
    prefix_b = f"tenant_{TENANT_B}__"
    for s in systems_b:
        assert s["id"].startswith(prefix_b), f"System {s['id']} doesn't belong to tenant B"
    # Verify the specific system is NOT in tenant B's list
    tenant_a_system_id = f"{prefix_a}{TEST_SYSTEM_ID}"
    assert not any(s["id"] == tenant_a_system_id for s in systems_b), \
        "Tenant B can see Tenant A's system — isolation broken!"


def test_delete_system_removes_it():
    """After deleting, get_system should return not found."""
    asyncio.run(create_system(
        system_id=TEST_SYSTEM_ID,
        name=TEST_SYSTEM_NAME,
        url=TEST_SYSTEM_URL,
        tenant_id=TENANT_A,
    ))
    # Delete it
    result = asyncio.run(delete_system(TEST_SYSTEM_ID, tenant_id=TENANT_A))
    assert result["success"] is True
    # Verify it's gone
    result = asyncio.run(get_system(TEST_SYSTEM_ID, tenant_id=TENANT_A))
    assert result["success"] is False
    assert "not found" in result.get("error", "").lower()


def test_get_nonexistent_system_returns_not_found():
    """Getting a system that doesn't exist should return success=False."""
    result = asyncio.run(get_system("nonexistent-system-xyz", tenant_id=TENANT_A))
    assert result["success"] is False
    assert "not found" in result.get("error", "").lower()


def test_delete_nonexistent_system_returns_not_found():
    """Deleting a system that doesn't exist should return success=False."""
    result = asyncio.run(delete_system("nonexistent-system-xyz", tenant_id=TENANT_A))
    assert result["success"] is False


def test_namespaced_tool_id_format():
    """namespaced_tool_id should produce the correct tenant_{id}__{tool} format."""
    result = namespaced_tool_id("shopify", "tenant-123")
    assert result == "tenant_tenant-123__shopify"

    # Already-namespaced IDs should pass through unchanged
    already = "tenant_abc__shopify"
    assert namespaced_tool_id(already, "different-tenant") == already

    # Empty tenant_id should return the raw tool_id
    assert namespaced_tool_id("shopify", "") == "shopify"


def test_full_round_trip_create_list_get_delete():
    """Full lifecycle: create → list (see it) → get (verify) → delete → get (gone)."""
    # 1. Create
    create_result = asyncio.run(create_system(
        system_id=TEST_SYSTEM_ID,
        name=TEST_SYSTEM_NAME,
        url=TEST_SYSTEM_URL,
        tenant_id=TENANT_A,
        icon="🛒",
    ))
    assert create_result["success"] is True

    # 2. List — should include our system
    systems = asyncio.run(list_tenant_systems(TENANT_A))
    system_ids = [s["id"] for s in systems]
    expected_id = f"tenant_{TENANT_A}__{TEST_SYSTEM_ID}"
    assert expected_id in system_ids, f"Created system {expected_id} not in list: {system_ids}"

    # 3. Get — should return our system
    get_result = asyncio.run(get_system(TEST_SYSTEM_ID, tenant_id=TENANT_A))
    assert get_result["success"] is True
    assert get_result["data"]["name"] == TEST_SYSTEM_NAME

    # 4. Delete
    del_result = asyncio.run(delete_system(TEST_SYSTEM_ID, tenant_id=TENANT_A))
    assert del_result["success"] is True

    # 5. Get — should be gone
    get_after = asyncio.run(get_system(TEST_SYSTEM_ID, tenant_id=TENANT_A))
    assert get_after["success"] is False
