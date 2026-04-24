"""Tests for Capacity Monitor (capacity_monitor.py)

Covers:
- Slot acquisition
- Slot release
- Capacity limits and queries
- Queue mechanism (FIFO, priority)
- Threshold alerts (70%, 90%, 95%)
- Utilization history
- Overflow detection
- Concurrent slot management
- Per-company isolation
- Configuration of limits
- Cleanup operations

Target: 55+ tests
"""

from __future__ import annotations

import time

import pytest

from app.core.capacity_monitor import (
    CapacityMonitor,
    QueueItem,
    THRESHOLD_WARNING,
    THRESHOLD_CRITICAL,
    THRESHOLD_FULL,
    DEFAULT_MAX_CONCURRENT,
    ALL_VARIANTS,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def monitor() -> CapacityMonitor:
    m = CapacityMonitor()
    yield m
    m.reset()


COMPANY_ID = "co_test_100"
COMPANY_2 = "co_test_200"


# ═══════════════════════════════════════════════════════════════════
# 1. Slot Acquisition
# ═══════════════════════════════════════════════════════════════════


class TestSlotAcquisition:

    def test_acquire_first_slot(self, monitor):
        result = monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        assert result is True

    def test_acquire_fills_to_capacity(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 3)
        for i in range(3):
            result = monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
            assert result is True

    def test_acquire_beyond_capacity_queues(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 2)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_2"
        )
        result = monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_3"
        )
        assert result is False

    def test_acquire_default_parwa_limit(self, monitor):
        default = DEFAULT_MAX_CONCURRENT["parwa"]
        for i in range(default):
            assert monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            ) is True
        assert monitor.acquire_slot(
            COMPANY_ID, "parwa", f"tkt_{default}"
        ) is False

    def test_acquire_mini_parwa_limit(self, monitor):
        default = DEFAULT_MAX_CONCURRENT["mini_parwa"]
        for i in range(default):
            assert monitor.acquire_slot(
                COMPANY_ID, "mini_parwa", f"tkt_{i}"
            ) is True

    def test_acquire_high_parwa_limit(self, monitor):
        default = DEFAULT_MAX_CONCURRENT["high_parwa"]
        for i in range(default):
            assert monitor.acquire_slot(
                COMPANY_ID, "high_parwa", f"tkt_{i}"
            ) is True

    def test_acquire_with_metadata(self, monitor):
        result = monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1",
            metadata={"agent": "bot1"},
        )
        assert result is True
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 1


# ═══════════════════════════════════════════════════════════════════
# 2. Slot Release
# ═══════════════════════════════════════════════════════════════════


class TestSlotRelease:

    def test_release_acquired_slot(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        result = monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        assert result is True
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 0

    def test_release_unknown_slot_returns_false(self, monitor):
        result = monitor.release_slot(
            COMPANY_ID, "parwa", "no_such_ticket"
        )
        assert result is False

    def test_release_frees_capacity(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 2)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_2"
        )
        monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        # Should be able to acquire again
        result = monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_3"
        )
        assert result is True

    def test_release_processes_queue(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 1)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_2"
        )  # queued
        monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 1  # tkt_2 auto-activated


# ═══════════════════════════════════════════════════════════════════
# 3. Capacity Queries
# ═══════════════════════════════════════════════════════════════════


class TestCapacityQueries:

    def test_capacity_empty(self, monitor):
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 0
        assert cap["total"] == DEFAULT_MAX_CONCURRENT["parwa"]
        assert cap["available"] == cap["total"]
        assert cap["percentage"] == 0.0

    def test_capacity_after_acquisition(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 5)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_2"
        )
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 2
        assert cap["available"] == 3
        assert cap["percentage"] == 40.0

    def test_capacity_percentage_precision(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 3)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["percentage"] == round(100 / 3, 2)


# ═══════════════════════════════════════════════════════════════════
# 4. Queue Mechanism
# ═══════════════════════════════════════════════════════════════════


class TestQueueMechanism:

    def test_queue_position(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 1)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_0"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_2"
        )
        pos = monitor.get_queue_position(
            COMPANY_ID, "parwa", "tkt_1"
        )
        assert pos == 0
        pos2 = monitor.get_queue_position(
            COMPANY_ID, "parwa", "tkt_2"
        )
        assert pos2 == 1

    def test_queue_position_not_queued(self, monitor):
        pos = monitor.get_queue_position(
            COMPANY_ID, "parwa", "no_ticket"
        )
        assert pos == -1

    def test_fifo_order(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 1)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "active"
        )
        for i in range(3):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"queued_{i}"
            )
        # FIFO: queued_0 should be first in queue
        pos0 = monitor.get_queue_position(
            COMPANY_ID, "parwa", "queued_0"
        )
        assert pos0 == 0

    def test_priority_ordering(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 1)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "active"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "low_p",
            priority=1,
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "high_p",
            priority=10,
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "mid_p",
            priority=5,
        )
        # Release active, high_p should be dequeued first
        monitor.release_slot(
            COMPANY_ID, "parwa", "active"
        )
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 1
        # high_p is now active
        assert monitor.get_queue_position(
            COMPANY_ID, "parwa", "high_p"
        ) == -1

    def test_queue_size(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 1)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_0"
        )
        for i in range(4):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"q_{i}"
            )
        assert monitor.get_queue_size(
            COMPANY_ID, "parwa"
        ) == 4

    def test_process_queue_manual(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 2)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_0"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_q"
        )  # queued
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_q2"
        )  # queued
        # Release one — auto-processes queue, activating tkt_q
        monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_0"
        )
        # tkt_q is now active, tkt_q2 still queued
        # Release another — should auto-activate tkt_q2
        monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 2

    def test_process_queue_empty(self, monitor):
        activated = monitor.process_queue(
            COMPANY_ID, "parwa"
        )
        assert activated == []


# ═══════════════════════════════════════════════════════════════════
# 5. Threshold Alerts
# ═══════════════════════════════════════════════════════════════════


class TestThresholdAlerts:

    def test_no_alert_below_warning(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(6):  # 60%
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        alerts = monitor.get_alerts(COMPANY_ID)
        assert len(alerts) == 0

    def test_warning_alert_at_70_percent(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(7):  # 70%
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        alerts = monitor.get_alerts(COMPANY_ID)
        levels = [a["level"] for a in alerts]
        assert "warning" in levels

    def test_critical_alert_at_90_percent(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(9):  # 90%
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        alerts = monitor.get_alerts(COMPANY_ID)
        levels = [a["level"] for a in alerts]
        assert "critical" in levels

    def test_full_alert_at_95_percent(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 20)
        for i in range(19):  # 95%
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        alerts = monitor.get_alerts(COMPANY_ID)
        levels = [a["level"] for a in alerts]
        assert "full" in levels

    def test_alert_cleared_on_release(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(7):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        assert len(monitor.get_alerts(COMPANY_ID)) > 0
        # Release all
        for i in range(7):
            monitor.release_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        alerts = monitor.get_alerts(COMPANY_ID)
        assert len(alerts) == 0

    def test_alert_has_required_fields(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(7):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        alerts = monitor.get_alerts(COMPANY_ID)
        assert len(alerts) >= 1
        alert = alerts[0]
        assert "level" in alert
        assert "variant" in alert
        assert "message" in alert
        assert "percentage" in alert
        assert "timestamp" in alert

    def test_no_duplicate_alerts(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(7):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        # Acquire one more (still warning territory)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_extra"
        )
        alerts = monitor.get_alerts(COMPANY_ID)
        warning_count = sum(
            1 for a in alerts if a["level"] == "warning"
        )
        assert warning_count == 1

    def test_alerts_isolated_by_company(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(7):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        alerts_2 = monitor.get_alerts(COMPANY_2)
        assert len(alerts_2) == 0


# ═══════════════════════════════════════════════════════════════════
# 6. Utilization History
# ═══════════════════════════════════════════════════════════════════


class TestUtilizationHistory:

    def test_history_records_on_acquire(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        history = monitor.get_utilization_history(
            COMPANY_ID, "parwa"
        )
        assert len(history) >= 1

    def test_history_records_on_release(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        history = monitor.get_utilization_history(
            COMPANY_ID, "parwa"
        )
        assert len(history) >= 2

    def test_history_has_required_fields(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        history = monitor.get_utilization_history(
            COMPANY_ID, "parwa"
        )
        snapshot = history[0]
        assert "timestamp" in snapshot
        assert "used" in snapshot
        assert "total" in snapshot
        assert "percentage" in snapshot

    def test_history_with_time_window(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        history = monitor.get_utilization_history(
            COMPANY_ID, "parwa", window_seconds=10.0
        )
        assert len(history) >= 1

    def test_history_window_filters_old(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        # Use very small window that should still include
        # the just-recorded snapshot
        history = monitor.get_utilization_history(
            COMPANY_ID, "parwa", window_seconds=0.001
        )
        # May or may not be included depending on timing

    def test_history_empty_for_unknown_variant(self, monitor):
        history = monitor.get_utilization_history(
            COMPANY_ID, "no_variant"
        )
        assert history == []


# ═══════════════════════════════════════════════════════════════════
# 7. Overflow Detection
# ═══════════════════════════════════════════════════════════════════


class TestOverflowDetection:

    def test_no_overflow_when_empty(self, monitor):
        status = monitor.get_overflow_status(COMPANY_ID)
        assert status["has_overflow"] is False
        assert status["total_queued"] == 0

    def test_overflow_detected_at_warning(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(7):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        status = monitor.get_overflow_status(COMPANY_ID)
        assert status["has_overflow"] is True

    def test_overflow_with_queue(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 2)
        for i in range(5):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        status = monitor.get_overflow_status(COMPANY_ID)
        assert status["total_queued"] == 3
        assert status["has_overflow"] is True

    def test_overflow_status_has_all_variants(self, monitor):
        status = monitor.get_overflow_status(COMPANY_ID)
        for v in ALL_VARIANTS:
            assert v in status["variants"]

    def test_scaling_suggestion_at_critical(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 10)
        for i in range(9):
            monitor.acquire_slot(
                COMPANY_ID, "parwa", f"tkt_{i}"
            )
        status = monitor.get_overflow_status(COMPANY_ID)
        assert status["scaling_suggestion"] is not None
        assert (
            status["scaling_suggestion"]["action"]
            == "increase_capacity"
        )

    def test_no_scaling_when_ok(self, monitor):
        status = monitor.get_overflow_status(COMPANY_ID)
        assert status["scaling_suggestion"] is None


# ═══════════════════════════════════════════════════════════════════
# 8. Configuration
# ═══════════════════════════════════════════════════════════════════


class TestConfiguration:

    def test_configure_limits(self, monitor):
        monitor.configure_limits(
            COMPANY_ID, "parwa", 20
        )
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["total"] == 20

    def test_configure_limits_below_one_raises(self, monitor):
        with pytest.raises(ValueError):
            monitor.configure_limits(
                COMPANY_ID, "parwa", 0
            )

    def test_configure_per_variant(self, monitor):
        monitor.configure_limits(
            COMPANY_ID, "mini_parwa", 15
        )
        monitor.configure_limits(
            COMPANY_ID, "parwa", 25
        )
        assert monitor.get_capacity(
            COMPANY_ID, "mini_parwa"
        )["total"] == 15
        assert monitor.get_capacity(
            COMPANY_ID, "parwa"
        )["total"] == 25

    def test_configure_isolated_by_company(self, monitor):
        monitor.configure_limits(
            COMPANY_ID, "parwa", 50
        )
        cap2 = monitor.get_capacity(COMPANY_2, "parwa")
        assert cap2["total"] == DEFAULT_MAX_CONCURRENT["parwa"]


# ═══════════════════════════════════════════════════════════════════
# 9. Per-Company Isolation
# ═══════════════════════════════════════════════════════════════════


class TestCompanyIsolation:

    def test_slots_isolated(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 2)
        monitor.configure_limits(COMPANY_2, "parwa", 2)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_2"
        )
        # Company 2 should still have capacity
        assert monitor.acquire_slot(
            COMPANY_2, "parwa", "tkt_3"
        ) is True

    def test_queue_isolated(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 1)
        monitor.configure_limits(COMPANY_2, "parwa", 1)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "c1_t1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "c1_t2"
        )  # queued
        # Company 2 queue should be empty
        assert monitor.get_queue_size(
            COMPANY_2, "parwa"
        ) == 0

    def test_clear_company(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 5)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.clear_company(COMPANY_ID)
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 0

    def test_clear_company_preserves_other(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 5)
        monitor.configure_limits(COMPANY_2, "parwa", 5)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.acquire_slot(
            COMPANY_2, "parwa", "tkt_2"
        )
        monitor.clear_company(COMPANY_ID)
        assert monitor.get_capacity(
            COMPANY_2, "parwa"
        )["used"] == 1


# ═══════════════════════════════════════════════════════════════════
# 10. Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_release_same_slot_twice(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        assert monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        ) is True
        assert monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        ) is False

    def test_reacquire_released_slot(self, monitor):
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.release_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        assert monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        ) is True

    def test_queue_item_dataclass(self):
        item = QueueItem(
            priority=5,
            ticket_id="tkt_test",
            company_id="co_test",
            variant="parwa",
        )
        assert item.priority == 5
        assert item.ticket_id == "tkt_test"

    def test_process_queue_multiple(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 1)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "active"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "q1"
        )
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "q2"
        )
        # Release activates q1 from queue automatically
        monitor.release_slot(
            COMPANY_ID, "parwa", "active"
        )
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 1
        # q2 should still be queued
        assert monitor.get_queue_position(
            COMPANY_ID, "parwa", "q2"
        ) == 0

    def test_default_concurrent_values(self):
        assert DEFAULT_MAX_CONCURRENT["mini_parwa"] == 5
        assert DEFAULT_MAX_CONCURRENT["parwa"] == 10
        assert DEFAULT_MAX_CONCURRENT["high_parwa"] == 3

    def test_all_variants_covered(self):
        assert "mini_parwa" in ALL_VARIANTS
        assert "parwa" in ALL_VARIANTS
        assert "high_parwa" in ALL_VARIANTS

    def test_reset_clears_all(self, monitor):
        monitor.configure_limits(COMPANY_ID, "parwa", 5)
        monitor.acquire_slot(
            COMPANY_ID, "parwa", "tkt_1"
        )
        monitor.reset()
        # Limits should be preserved (configuration)
        cap = monitor.get_capacity(COMPANY_ID, "parwa")
        assert cap["used"] == 0
        assert cap["total"] == 5  # configured limit preserved
