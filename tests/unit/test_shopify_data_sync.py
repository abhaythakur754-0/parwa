"""
PARWA Day 4 — Unit Tests for ShopifyDataSync Service

Tests the data sync service with mocked ShopifyClient and DB session.
Covers:
- Full sync (orders, products, customers)
- Incremental sync
- Single record sync
- Sync state management
- Error handling (BC-008)
- Data processing and normalization

Run: pytest tests/unit/test_shopify_data_sync.py -v
"""

import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.clients.shopify_client import ShopifyClient, ShopifyResult
from app.services.shopify_data_sync import (
    ShopifyDataSync,
    SyncResult,
    SYNC_STATUS_IDLE,
    SYNC_STATUS_RUNNING,
    SYNC_STATUS_COMPLETED,
    SYNC_STATUS_FAILED,
    SYNC_STATUS_PARTIAL,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.flush = MagicMock()
    return db


@pytest.fixture
def mock_client():
    """Create a mock ShopifyClient."""
    client = MagicMock(spec=ShopifyClient)
    client.shop_domain = "test.myshopify.com"
    return client


@pytest.fixture
def sync_service(mock_db, mock_client):
    """Create a ShopifyDataSync instance with mocked dependencies."""
    return ShopifyDataSync(
        db=mock_db,
        shopify_client=mock_client,
        company_id="comp_123",
        integration_id="int_456",
    )


# Sample data
SAMPLE_ORDERS = [
    {"id": 1, "email": "a@test.com", "total_price": "10.00", "currency": "USD", "created_at": "2026-01-01T00:00:00Z"},
    {"id": 2, "email": "b@test.com", "total_price": "20.00", "currency": "USD", "created_at": "2026-01-02T00:00:00Z"},
    {"id": 3, "email": "c@test.com", "total_price": "30.00", "currency": "USD", "created_at": "2026-01-03T00:00:00Z"},
]

SAMPLE_PRODUCTS = [
    {"id": 10, "title": "Product A", "vendor": "ACME", "product_type": "Widget", "status": "active", "created_at": "2026-01-01T00:00:00Z"},
    {"id": 20, "title": "Product B", "vendor": "ACME", "product_type": "Gadget", "status": "active", "created_at": "2026-01-02T00:00:00Z"},
]

SAMPLE_CUSTOMERS = [
    {"id": 100, "email": "alice@test.com", "first_name": "Alice", "last_name": "Smith", "orders_count": 5, "total_spent": "150.00", "created_at": "2026-01-01T00:00:00Z"},
    {"id": 200, "email": "bob@test.com", "first_name": "Bob", "last_name": "Jones", "orders_count": 3, "total_spent": "75.00", "created_at": "2026-01-02T00:00:00Z"},
]


# ═══════════════════════════════════════════════════════════════════
# Test: SyncResult
# ═══════════════════════════════════════════════════════════════════

class TestSyncResult:
    """Tests for SyncResult data class."""

    def test_success_result(self):
        result = SyncResult(
            status=SYNC_STATUS_COMPLETED,
            orders_synced=10,
            products_synced=5,
            customers_synced=3,
        )
        assert result.status == SYNC_STATUS_COMPLETED
        assert result.orders_synced == 10
        assert result.products_synced == 5
        assert result.customers_synced == 3

    def test_to_dict(self):
        result = SyncResult(
            status=SYNC_STATUS_COMPLETED,
            orders_synced=10,
            products_synced=5,
            customers_synced=3,
        )
        d = result.to_dict()
        assert d["status"] == SYNC_STATUS_COMPLETED
        assert d["total_synced"] == 18  # 10 + 5 + 3

    def test_result_with_errors(self):
        result = SyncResult(
            status=SYNC_STATUS_PARTIAL,
            errors=["Orders sync failed: timeout"],
        )
        assert len(result.errors) == 1
        assert "timeout" in result.errors[0]


# ═══════════════════════════════════════════════════════════════════
# Test: Full Sync
# ═══════════════════════════════════════════════════════════════════

class TestFullSync:
    """Tests for full_sync method."""

    @pytest.mark.asyncio
    async def test_full_sync_success(self, sync_service, mock_client):
        """Full sync should process orders, products, and customers."""
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_ORDERS))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_PRODUCTS))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_CUSTOMERS))

        result = await sync_service.full_sync()

        assert result.status == SYNC_STATUS_COMPLETED
        assert result.orders_synced == 3
        assert result.products_synced == 2
        assert result.customers_synced == 2
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_full_sync_partial_failure(self, sync_service, mock_client):
        """Full sync should return partial if one resource fails."""
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_ORDERS))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(success=False, error="API error"))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_CUSTOMERS))

        result = await sync_service.full_sync()

        assert result.status == SYNC_STATUS_PARTIAL
        assert result.orders_synced == 3
        assert result.products_synced == 0
        assert result.customers_synced == 2
        assert len(result.errors) == 1
        assert "Products sync failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_full_sync_all_fail(self, sync_service, mock_client):
        """Full sync should return failed if all resources fail."""
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(success=False, error="Orders failed"))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(success=False, error="Products failed"))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(success=False, error="Customers failed"))

        result = await sync_service.full_sync()

        assert result.status == SYNC_STATUS_FAILED
        assert result.orders_synced == 0
        assert len(result.errors) == 3

    @pytest.mark.asyncio
    async def test_full_sync_empty_data(self, sync_service, mock_client):
        """Full sync with empty data should succeed with zero counts."""
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(success=True, data=[]))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(success=True, data=[]))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(success=True, data=[]))

        result = await sync_service.full_sync()

        assert result.status == SYNC_STATUS_COMPLETED
        assert result.orders_synced == 0
        assert result.products_synced == 0
        assert result.customers_synced == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Incremental Sync
# ═══════════════════════════════════════════════════════════════════

class TestIncrementalSync:
    """Tests for incremental_sync method."""

    @pytest.mark.asyncio
    async def test_incremental_sync_success(self, sync_service, mock_client):
        """Incremental sync should fetch only new records."""
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(success=True, data=[SAMPLE_ORDERS[0]]))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(success=True, data=[SAMPLE_PRODUCTS[0]]))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(success=True, data=[SAMPLE_CUSTOMERS[0]]))

        result = await sync_service.incremental_sync()

        assert result.status == SYNC_STATUS_COMPLETED
        assert result.orders_synced >= 1

    @pytest.mark.asyncio
    async def test_incremental_sync_no_since_id(self, sync_service, mock_client):
        """Without since_id, incremental should fall back to full for each resource."""
        # No sync state → no since_id → falls back to _sync_all_*
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_ORDERS))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_PRODUCTS))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_CUSTOMERS))

        result = await sync_service.incremental_sync()

        assert result.status == SYNC_STATUS_COMPLETED

    @pytest.mark.asyncio
    async def test_incremental_sync_partial_failure(self, sync_service, mock_client):
        """Incremental sync should handle partial failures."""
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_ORDERS))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(success=False, error="API error"))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(success=True, data=SAMPLE_CUSTOMERS))

        result = await sync_service.incremental_sync()

        assert result.status == SYNC_STATUS_PARTIAL


# ═══════════════════════════════════════════════════════════════════
# Test: Single Record Sync
# ═══════════════════════════════════════════════════════════════════

class TestSingleRecordSync:
    """Tests for individual record sync methods."""

    @pytest.mark.asyncio
    async def test_sync_order_success(self, sync_service, mock_client):
        mock_client.get_order = AsyncMock(return_value=ShopifyResult(
            success=True,
            data={"id": 123, "email": "test@test.com", "total_price": "99.99"},
        ))

        result = await sync_service.sync_order("123")

        assert result.status == SYNC_STATUS_COMPLETED
        assert result.orders_synced == 1

    @pytest.mark.asyncio
    async def test_sync_order_failure(self, sync_service, mock_client):
        mock_client.get_order = AsyncMock(return_value=ShopifyResult(
            success=False,
            error="Order not found",
        ))

        result = await sync_service.sync_order("999")

        assert result.status == SYNC_STATUS_FAILED
        assert result.orders_synced == 0
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_sync_product_success(self, sync_service, mock_client):
        mock_client.get_product = AsyncMock(return_value=ShopifyResult(
            success=True,
            data={"id": 456, "title": "Widget"},
        ))

        result = await sync_service.sync_product("456")

        assert result.status == SYNC_STATUS_COMPLETED
        assert result.products_synced == 1

    @pytest.mark.asyncio
    async def test_sync_product_failure(self, sync_service, mock_client):
        mock_client.get_product = AsyncMock(return_value=ShopifyResult(
            success=False,
            error="Product not found",
        ))

        result = await sync_service.sync_product("999")

        assert result.status == SYNC_STATUS_FAILED
        assert result.products_synced == 0

    @pytest.mark.asyncio
    async def test_sync_customer_success(self, sync_service, mock_client):
        mock_client.get_customer = AsyncMock(return_value=ShopifyResult(
            success=True,
            data={"id": 789, "email": "alice@test.com"},
        ))

        result = await sync_service.sync_customer("789")

        assert result.status == SYNC_STATUS_COMPLETED
        assert result.customers_synced == 1

    @pytest.mark.asyncio
    async def test_sync_customer_failure(self, sync_service, mock_client):
        mock_client.get_customer = AsyncMock(return_value=ShopifyResult(
            success=False,
            error="Customer not found",
        ))

        result = await sync_service.sync_customer("999")

        assert result.status == SYNC_STATUS_FAILED
        assert result.customers_synced == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Data Processing
# ═══════════════════════════════════════════════════════════════════

class TestDataProcessing:
    """Tests for data processing and normalization methods."""

    def test_process_order_data_valid(self, sync_service):
        order = {"id": 1, "email": "test@test.com", "total_price": "99.99", "currency": "USD"}
        result = sync_service._process_order_data(order)
        assert result is True

    def test_process_order_data_missing_id(self, sync_service):
        order = {"email": "test@test.com"}
        result = sync_service._process_order_data(order)
        assert result is False

    def test_process_order_data_empty_dict(self, sync_service):
        result = sync_service._process_order_data({})
        assert result is False

    def test_process_product_data_valid(self, sync_service):
        product = {"id": 1, "title": "Widget", "vendor": "ACME"}
        result = sync_service._process_product_data(product)
        assert result is True

    def test_process_product_data_missing_id(self, sync_service):
        product = {"title": "No ID"}
        result = sync_service._process_product_data(product)
        assert result is False

    def test_process_customer_data_valid(self, sync_service):
        customer = {"id": 1, "email": "test@test.com", "orders_count": 5}
        result = sync_service._process_customer_data(customer)
        assert result is True

    def test_process_customer_data_missing_id(self, sync_service):
        customer = {"email": "test@test.com"}
        result = sync_service._process_customer_data(customer)
        assert result is False

    def test_process_order_data_exception(self, sync_service):
        """Should handle exceptions gracefully (BC-008)."""
        # Pass something that could cause an error
        result = sync_service._process_order_data(None)
        assert result is False

    def test_process_product_data_exception(self, sync_service):
        result = sync_service._process_product_data(None)
        assert result is False

    def test_process_customer_data_exception(self, sync_service):
        result = sync_service._process_customer_data(None)
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# Test: Sync State Management
# ═══════════════════════════════════════════════════════════════════

class TestSyncStateManagement:
    """Tests for sync state read/write operations."""

    def test_get_sync_state_no_integration(self, sync_service, mock_db):
        """Should return empty dict when no integration record found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        state = sync_service._get_sync_state()
        assert state == {}

    def test_get_sync_state_with_data(self, sync_service, mock_db):
        """Should return sync state from integration settings."""
        mock_integration = MagicMock()
        mock_integration.settings = json.dumps({
            "sync_state": {"last_order_sync": "2026-01-01", "total_orders_synced": 42}
        })
        mock_db.query.return_value.filter.return_value.first.return_value = mock_integration

        state = sync_service._get_sync_state()
        assert state["last_order_sync"] == "2026-01-01"
        assert state["total_orders_synced"] == 42

    def test_get_sync_state_invalid_json(self, sync_service, mock_db):
        """Should handle invalid JSON gracefully."""
        mock_integration = MagicMock()
        mock_integration.settings = "not json"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_integration

        state = sync_service._get_sync_state()
        assert state == {}

    def test_update_sync_state_no_integration(self, sync_service, mock_db):
        """Should silently skip when no integration found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        # Should not raise
        sync_service._update_sync_state({"status": "running"})

    def test_update_sync_state_success(self, sync_service, mock_db):
        """Should update settings JSON with new sync state."""
        mock_integration = MagicMock()
        mock_integration.settings = json.dumps({"sync_state": {"existing_key": "value"}})
        mock_db.query.return_value.filter.return_value.first.return_value = mock_integration

        sync_service._update_sync_state({"status": "completed"})

        # Verify settings was updated
        updated_settings = json.loads(mock_integration.settings)
        assert updated_settings["sync_state"]["status"] == "completed"
        assert updated_settings["sync_state"]["existing_key"] == "value"
        mock_db.flush.assert_called()

    def test_get_sync_status(self, sync_service, mock_db):
        """get_sync_status should return comprehensive status info."""
        mock_integration = MagicMock()
        mock_integration.settings = json.dumps({
            "sync_state": {
                "status": "completed",
                "last_full_sync": "2026-01-01",
                "total_orders_synced": 10,
                "total_products_synced": 5,
                "total_customers_synced": 8,
            }
        })
        mock_db.query.return_value.filter.return_value.first.return_value = mock_integration

        status = sync_service.get_sync_status()
        assert status["company_id"] == "comp_123"
        assert status["integration_id"] == "int_456"
        assert status["shop_domain"] == "test.myshopify.com"
        assert status["status"] == "completed"
        assert status["total_orders_synced"] == 10


# ═══════════════════════════════════════════════════════════════════
# Test: No Integration ID
# ═══════════════════════════════════════════════════════════════════

class TestNoIntegrationId:
    """Tests for behavior when integration_id is not provided."""

    def test_get_sync_state_no_id(self, mock_db, mock_client):
        service = ShopifyDataSync(
            db=mock_db,
            shopify_client=mock_client,
            company_id="comp_123",
            integration_id="",  # No integration ID
        )
        state = service._get_sync_state()
        assert state == {}

    def test_update_sync_state_no_id(self, mock_db, mock_client):
        service = ShopifyDataSync(
            db=mock_db,
            shopify_client=mock_client,
            company_id="comp_123",
            integration_id="",
        )
        # Should not raise and should not call db
        service._update_sync_state({"status": "running"})
        mock_db.flush.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# Test: Pagination in Batch Sync
# ═══════════════════════════════════════════════════════════════════

class TestBatchSyncPagination:
    """Tests for pagination handling in batch sync."""

    @pytest.mark.asyncio
    async def test_sync_all_orders_under_limit(self, sync_service, mock_client):
        """Under 250 orders should not trigger pagination."""
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(
            success=True, data=SAMPLE_ORDERS,
        ))

        count = await sync_service._sync_all_orders()
        assert count == 3
        # Should only call list_orders once
        assert mock_client.list_orders.call_count == 1

    @pytest.mark.asyncio
    async def test_sync_all_orders_pagination(self, sync_service, mock_client):
        """Orders at page limit should trigger pagination."""
        # First page: 250 items (IDs 1-250 to avoid id=0 being falsy)
        first_page = [{"id": i, "email": f"test{i}@test.com", "total_price": "10", "currency": "USD"} for i in range(1, 251)]
        # Second page: 2 more items
        second_page = [
            {"id": 251, "email": "extra1@test.com", "total_price": "10", "currency": "USD"},
            {"id": 252, "email": "extra2@test.com", "total_price": "10", "currency": "USD"},
        ]

        async def mock_list_orders(**kwargs):
            since_id = kwargs.get("since_id")
            if since_id:
                return ShopifyResult(success=True, data=second_page)
            return ShopifyResult(success=True, data=first_page)

        mock_client.list_orders = mock_list_orders

        count = await sync_service._sync_all_orders()
        # First page (250) + second page (2) = 252 total
        assert count == 252
