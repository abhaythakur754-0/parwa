"""Tests for Cost Optimization modules."""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCostMonitor:
    """Tests for cost monitoring functionality."""

    def test_cost_monitor_initializes(self):
        """Test cost monitor initializes correctly."""
        from backend.optimization.cost_monitor import CostMonitor
        monitor = CostMonitor()
        assert monitor is not None
        assert len(monitor.alerts) > 0

    def test_track_cost(self):
        """Test tracking a cost metric."""
        from backend.optimization.cost_monitor import CostMonitor
        monitor = CostMonitor()
        
        metric = monitor.track_cost(
            service="compute",
            resource_type="cpu",
            cost_usd=100.0,
            tags={"environment": "prod"},
        )
        
        assert metric.service == "compute"
        assert metric.cost_usd == 100.0

    def test_get_daily_costs(self):
        """Test getting daily costs."""
        from backend.optimization.cost_monitor import CostMonitor
        monitor = CostMonitor()
        monitor.track_cost("compute", "cpu", 50.0)
        monitor.track_cost("storage", "disk", 30.0)
        
        daily = monitor.get_daily_costs()
        assert isinstance(daily, dict)

    def test_get_total_cost(self):
        """Test getting total cost."""
        from backend.optimization.cost_monitor import CostMonitor
        monitor = CostMonitor()
        monitor.track_cost("compute", "cpu", 100.0)
        monitor.track_cost("storage", "disk", 50.0)
        
        total = monitor.get_total_cost()
        assert total == 150.0

    def test_get_cost_report(self):
        """Test generating cost report."""
        from backend.optimization.cost_monitor import CostMonitor
        monitor = CostMonitor()
        monitor.track_cost("compute", "cpu", 100.0)
        
        report = monitor.get_cost_report()
        assert "total_7_days" in report
        assert "total_30_days" in report


class TestResourceOptimizer:
    """Tests for resource optimization."""

    def test_optimizer_initializes(self):
        """Test optimizer initializes correctly."""
        from backend.optimization.resource_optimizer import ResourceOptimizer
        optimizer = ResourceOptimizer()
        assert optimizer is not None

    def test_detect_underutilized_cpu(self):
        """Test detection of underutilized CPU."""
        from backend.optimization.resource_optimizer import (
            ResourceOptimizer, ResourceUsage
        )
        optimizer = ResourceOptimizer()
        
        usage = ResourceUsage(
            resource_name="test-pod",
            resource_type="Deployment",
            cpu_usage_percent=15.0,
            memory_usage_percent=25.0,
            cpu_request=2.0,
            memory_request=4.0,
            cpu_limit=4.0,
            memory_limit=8.0,
            cost_usd_per_hour=0.50,
        )
        
        optimizer.add_resource(usage)
        recs = optimizer.get_recommendations()
        assert len(recs) > 0


class TestAPIUsageTracker:
    """Tests for API usage tracking."""

    def test_track_api_call(self):
        """Test tracking an API call."""
        from backend.optimization.cost_monitor import APIUsageTracker
        tracker = APIUsageTracker()
        
        tracker.track_api_call(
            api_name="openrouter",
            endpoint="/chat/completions",
            tokens_used=1000,
            cost_usd=0.02,
        )
        
        assert "openrouter" in tracker.usage


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
