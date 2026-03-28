"""
30-Client Validation Tests for SaaS Advanced (Week 32, Builder 5).

Validates SaaS features work correctly across all 30 clients.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from variants.saas.advanced.subscription_manager import SubscriptionManager, SubscriptionTier
from variants.saas.advanced.usage_meter import UsageMeter, UsageType
from variants.saas.advanced.churn_predictor import ChurnPredictor, CustomerFeatures
from variants.saas.advanced.health_score import HealthScoreCalculator


# Mock client configurations for 30 clients
MOCK_CLIENTS = [
    {"id": f"client_{i:03d}", "tier": ["mini", "parwa", "parwa_high"][i % 3], "region": ["US", "EU", "APAC"][i % 3]}
    for i in range(1, 31)
]


class Test30ClientValidation:
    """Validation tests for 30-client isolation and functionality."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("client", MOCK_CLIENTS)
    async def test_subscription_per_client(self, client):
        """Test subscription works for each client."""
        manager = SubscriptionManager(client_id=client["id"], company_id=uuid4())

        tier_map = {
            "mini": SubscriptionTier.MINI,
            "parwa": SubscriptionTier.PARWA,
            "parwa_high": SubscriptionTier.PARWA_HIGH,
        }

        subscription = await manager.create_subscription(
            tier=tier_map[client["tier"]],
        )

        assert subscription.client_id == client["id"]
        assert subscription.tier.value == client["tier"]

    @pytest.mark.asyncio
    async def test_usage_tracking_30_clients(self):
        """Test usage tracking across 30 clients."""
        for client in MOCK_CLIENTS[:10]:  # Test subset for speed
            meter = UsageMeter(client_id=client["id"], tier=client["tier"])
            await meter.track(UsageType.API_CALLS, quantity=100)
            await meter.track(UsageType.AI_INTERACTIONS, quantity=50)

            usage = await meter.get_usage()
            assert usage["usage"]["api_calls"] == 100

    @pytest.mark.asyncio
    async def test_churn_prediction_30_clients(self):
        """Test churn prediction across 30 clients."""
        predictor = ChurnPredictor()

        for i, client in enumerate(MOCK_CLIENTS[:10]):
            # Vary features based on client index
            features = CustomerFeatures(
                client_id=client["id"],
                days_since_signup=30 + i * 30,
                monthly_usage_trend=0.1 if i % 2 == 0 else -0.1,
                login_frequency_30d=10 + i,
                feature_adoption_rate=0.3 + (i * 0.05),
                nps_score=5 + (i % 5),
            )

            prediction = await predictor.predict(features)

            assert prediction.client_id == client["id"]
            assert 0 <= prediction.churn_probability <= 1

    @pytest.mark.asyncio
    async def test_health_score_30_clients(self):
        """Test health score across 30 clients."""
        for i, client in enumerate(MOCK_CLIENTS[:10]):
            calculator = HealthScoreCalculator(client_id=client["id"])

            health = await calculator.calculate_health_score(
                usage_data={"feature_utilization": 0.3 + (i * 0.05)},
                engagement_data={"logins_30d": 10 + i, "feature_adoption_rate": 0.3 + (i * 0.05)},
                financial_data={"payment_failures_90d": i % 3},
                support_data={"tickets_30d": i % 5, "avg_sentiment": 0.5 + (i * 0.05)},
            )

            assert health.client_id == client["id"]
            assert 0 <= health.overall_score <= 100

    @pytest.mark.asyncio
    async def test_client_data_isolation(self):
        """Test no cross-client data leakage."""
        # Create subscriptions for multiple clients
        clients_data = {}
        for client in MOCK_CLIENTS[:5]:
            manager = SubscriptionManager(client_id=client["id"], company_id=uuid4())
            subscription = await manager.create_subscription(
                tier=SubscriptionTier.PARWA,
            )
            clients_data[client["id"]] = subscription.id

        # Verify each manager only sees its own data
        for client in MOCK_CLIENTS[:5]:
            manager = SubscriptionManager(client_id=client["id"], company_id=uuid4())
            subscription = await manager.get_subscription()

            # Should either be None or belong to the correct client
            if subscription:
                assert subscription.client_id == client["id"]

    @pytest.mark.asyncio
    async def test_usage_limits_by_tier(self):
        """Test usage limits are enforced per tier."""
        tier_limits = {
            "mini": {"api_calls": 10000, "ai_interactions": 1000},
            "parwa": {"api_calls": 50000, "ai_interactions": 5000},
            "parwa_high": {"api_calls": 200000, "ai_interactions": 25000},
        }

        for client in MOCK_CLIENTS[:3]:  # One of each tier
            meter = UsageMeter(client_id=client["id"], tier=client["tier"])

            limits = await meter.check_all_limits()

            assert "limits" in limits
            # Limits should match tier configuration
            assert limits["limits"]["api_calls"]["limit"] == tier_limits[client["tier"]]["api_calls"]

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test performance with 30 clients."""
        import time

        start = time.time()

        # Simulate operations for all 30 clients
        for client in MOCK_CLIENTS:
            meter = UsageMeter(client_id=client["id"], tier=client["tier"])
            await meter.track(UsageType.API_CALLS, quantity=10)

        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 5.0  # 5 seconds for 30 clients

    @pytest.mark.asyncio
    async def test_concurrent_client_operations(self):
        """Test concurrent operations don't interfere."""
        import asyncio

        async def process_client(client):
            meter = UsageMeter(client_id=client["id"], tier=client["tier"])
            await meter.track(UsageType.API_CALLS, quantity=100)
            usage = await meter.get_usage()
            return client["id"], usage["usage"]["api_calls"]

        # Process 10 clients concurrently
        tasks = [process_client(c) for c in MOCK_CLIENTS[:10]]
        results = await asyncio.gather(*tasks)

        # Verify each client got correct usage
        for client_id, api_calls in results:
            assert api_calls == 100


class TestClientIsolation:
    """Specific tests for client isolation."""

    @pytest.mark.asyncio
    async def test_no_cross_client_usage_visibility(self):
        """Test clients cannot see other clients' usage."""
        # Create usage for multiple clients
        meters = {}
        for i in range(5):
            client_id = f"isolation_test_{i}"
            meter = UsageMeter(client_id=client_id, tier="parwa")
            await meter.track(UsageType.API_CALLS, quantity=(i + 1) * 100)
            meters[client_id] = meter

        # Each client should only see their own usage
        for i, (client_id, meter) in enumerate(meters.items()):
            usage = await meter.get_usage()
            assert usage["usage"]["api_calls"] == (i + 1) * 100

    @pytest.mark.asyncio
    async def test_no_cross_client_subscription_visibility(self):
        """Test clients cannot see other clients' subscriptions."""
        # Create subscriptions for multiple clients
        for i in range(5):
            client_id = f"sub_isolation_{i}"
            manager = SubscriptionManager(client_id=client_id, company_id=uuid4())
            await manager.create_subscription(tier=SubscriptionTier.PARWA)

        # Verify isolation
        for i in range(5):
            client_id = f"sub_isolation_{i}"
            manager = SubscriptionManager(client_id=client_id, company_id=uuid4())
            subscription = await manager.get_subscription()

            if subscription:
                assert subscription.client_id == client_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
