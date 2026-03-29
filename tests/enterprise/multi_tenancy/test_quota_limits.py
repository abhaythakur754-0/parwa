"""
Tests for Resource Quotas and Limits
"""

import pytest
from datetime import datetime, timedelta
from enterprise.multi_tenancy.quota_manager import (
    QuotaManager, ResourceType, QuotaPeriod, Quota, QuotaUsage
)
from enterprise.multi_tenancy.limit_enforcer import (
    LimitEnforcer, EnforcementAction, ViolationSeverity, LimitViolation
)
from enterprise.multi_tenancy.usage_tracker import (
    UsageTracker, AggregationPeriod, UsageRecord
)


class TestQuotaManager:
    """Tests for QuotaManager"""

    @pytest.fixture
    def manager(self):
        return QuotaManager()

    def test_create_quota(self, manager):
        quota = manager.create_quota(
            tenant_id="tenant_001",
            resource_type=ResourceType.API_REQUESTS,
            limit=1000,
            period=QuotaPeriod.DAILY
        )
        assert quota.quota_id is not None
        assert quota.limit == 1000

    def test_get_quota(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        quota = manager.get_quota("tenant_001", ResourceType.API_REQUESTS)
        assert quota is not None

    def test_get_quota_not_found(self, manager):
        quota = manager.get_quota("tenant_999", ResourceType.API_REQUESTS)
        assert quota is None

    def test_check_quota_allowed(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        result = manager.check_quota("tenant_001", ResourceType.API_REQUESTS, 100)
        assert result["allowed"] is True

    def test_check_quota_exceeded(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 100, hard_limit=True)
        manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 100)
        result = manager.check_quota("tenant_001", ResourceType.API_REQUESTS, 1)
        assert result["allowed"] is False

    def test_consume_quota(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        result = manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 10)
        assert result["consumed"] == 10
        assert result["new_used"] == 10

    def test_release_quota(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 50)
        manager.release_quota("tenant_001", ResourceType.API_REQUESTS, 20)

        quota = manager.get_quota("tenant_001", ResourceType.API_REQUESTS)
        assert quota.used == 30

    def test_update_quota_limit(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        manager.update_quota_limit("tenant_001", ResourceType.API_REQUESTS, 2000)

        quota = manager.get_quota("tenant_001", ResourceType.API_REQUESTS)
        assert quota.limit == 2000

    def test_get_tenant_quotas(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        manager.create_quota("tenant_001", ResourceType.STORAGE_BYTES, 1000000)

        quotas = manager.get_tenant_quotas("tenant_001")
        assert len(quotas) == 2

    def test_get_usage_history(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 10)
        manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 20)

        history = manager.get_usage_history("tenant_001")
        assert len(history) == 2

    def test_get_quota_summary(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 100)

        summary = manager.get_quota_summary("tenant_001")
        assert summary["total_quotas"] == 1
        assert summary["quotas"][0]["used"] == 100

    def test_delete_quota(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        result = manager.delete_quota("tenant_001", ResourceType.API_REQUESTS)
        assert result is True
        assert manager.get_quota("tenant_001", ResourceType.API_REQUESTS) is None

    def test_quota_warning_threshold(self, manager):
        manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 100, warn_threshold=0.8)
        manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 85)

        quota = manager.get_quota("tenant_001", ResourceType.API_REQUESTS)
        assert quota.is_warning is True


class TestLimitEnforcer:
    """Tests for LimitEnforcer"""

    @pytest.fixture
    def enforcer(self):
        manager = QuotaManager()
        return LimitEnforcer(quota_manager=manager, default_action=EnforcementAction.BLOCK)

    def test_enforce_allowed(self, enforcer):
        enforcer.quota_manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        result = enforcer.enforce("tenant_001", ResourceType.API_REQUESTS, 10)
        assert result["allowed"] is True

    def test_enforce_blocked(self, enforcer):
        enforcer.quota_manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 10, hard_limit=True)
        enforcer.quota_manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 10)

        result = enforcer.enforce("tenant_001", ResourceType.API_REQUESTS, 1)
        assert result["allowed"] is False
        assert result["reason"] == "limit_exceeded"

    def test_set_enforcement_rule(self, enforcer):
        enforcer.set_enforcement_rule(ResourceType.API_REQUESTS, EnforcementAction.THROTTLE)
        assert enforcer._get_enforcement_action(ResourceType.API_REQUESTS) == EnforcementAction.THROTTLE

    def test_throttle_application(self, enforcer):
        enforcer.set_enforcement_rule(ResourceType.API_REQUESTS, EnforcementAction.THROTTLE)
        enforcer.quota_manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 10, hard_limit=True)
        enforcer.quota_manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 10)

        # First violation triggers throttle
        result = enforcer.enforce("tenant_001", ResourceType.API_REQUESTS, 1)
        assert result["action"] == "throttle"

    def test_get_violations(self, enforcer):
        enforcer.quota_manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 5, hard_limit=True)
        enforcer.quota_manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 5)
        enforcer.enforce("tenant_001", ResourceType.API_REQUESTS, 1)

        violations = enforcer.get_violations(tenant_id="tenant_001")
        assert len(violations) == 1

    def test_clear_throttle(self, enforcer):
        enforcer.set_enforcement_rule(ResourceType.API_REQUESTS, EnforcementAction.THROTTLE)
        enforcer.quota_manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 5, hard_limit=True)
        enforcer.quota_manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 5)
        enforcer.enforce("tenant_001", ResourceType.API_REQUESTS, 1)

        result = enforcer.clear_throttle("tenant_001", ResourceType.API_REQUESTS)
        assert result is True

    def test_get_throttle_status(self, enforcer):
        status = enforcer.get_throttle_status("tenant_001")
        assert status["tenant_id"] == "tenant_001"

    def test_get_metrics(self, enforcer):
        enforcer.quota_manager.create_quota("tenant_001", ResourceType.API_REQUESTS, 1000)
        enforcer.enforce("tenant_001", ResourceType.API_REQUESTS, 10)

        metrics = enforcer.get_metrics()
        assert metrics["total_checks"] == 1


class TestUsageTracker:
    """Tests for UsageTracker"""

    @pytest.fixture
    def tracker(self):
        return UsageTracker()

    def test_track(self, tracker):
        record = tracker.track(
            tenant_id="tenant_001",
            resource_type=ResourceType.API_REQUESTS,
            amount=10
        )
        assert record.record_id is not None
        assert record.amount == 10

    def test_get_current_usage(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 20)

        usage = tracker.get_current_usage("tenant_001")
        assert usage["api_requests"] == 30

    def test_get_usage_history(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 20)

        history = tracker.get_usage_history("tenant_001")
        assert len(history) == 2

    def test_get_usage_summary(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 20)
        tracker.track("tenant_001", ResourceType.STORAGE_BYTES, 1000)

        summary = tracker.get_usage_summary("tenant_001")
        assert summary["total_records"] == 3
        assert "api_requests" in summary["by_resource"]

    def test_get_trend(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)

        trend = tracker.get_trend("tenant_001", ResourceType.API_REQUESTS, periods=7)
        assert len(trend) == 7

    def test_get_peak_usage(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 50)
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 20)

        peak = tracker.get_peak_usage("tenant_001", ResourceType.API_REQUESTS)
        assert peak["peak"] == 50

    def test_compare_periods(self, tracker):
        now = datetime.utcnow()
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 100)

        comparison = tracker.compare_periods(
            tenant_id="tenant_001",
            resource_type=ResourceType.API_REQUESTS,
            period1_start=now - timedelta(days=2),
            period1_end=now - timedelta(days=1),
            period2_start=now - timedelta(days=1),
            period2_end=now
        )
        assert "change" in comparison
        assert "change_percent" in comparison

    def test_reset_current_usage(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)
        tracker.reset_current_usage("tenant_001")

        usage = tracker.get_current_usage("tenant_001")
        assert usage == {} or usage.get("api_requests", 0) == 0

    def test_get_metrics(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)

        metrics = tracker.get_metrics()
        assert metrics["total_records"] == 1

    def test_export_usage(self, tracker):
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 10)

        export = tracker.export_usage("tenant_001", format="json")
        assert "record_id" in export


class TestQuotaIntegration:
    """Integration tests"""

    def test_full_quota_workflow(self):
        # Setup
        quota_manager = QuotaManager()
        enforcer = LimitEnforcer(quota_manager)
        tracker = UsageTracker()

        # Create quota
        quota_manager.create_quota(
            tenant_id="tenant_001",
            resource_type=ResourceType.API_REQUESTS,
            limit=100,
            period=QuotaPeriod.DAILY
        )

        # Track usage
        tracker.track("tenant_001", ResourceType.API_REQUESTS, 50)

        # Check and consume
        result = quota_manager.consume_quota("tenant_001", ResourceType.API_REQUESTS, 30)
        assert result["consumed"] == 30

        # Enforce
        enforce_result = enforcer.enforce("tenant_001", ResourceType.API_REQUESTS, 1)
        assert enforce_result["allowed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
