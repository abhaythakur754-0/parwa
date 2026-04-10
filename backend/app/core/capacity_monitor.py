"""
Capacity Monitor (F-069) — Workflow execution capacity tracking.

Tracks concurrent workflow executions per company with per-variant
capacity tracking, threshold alerts, FIFO+priority queuing, and
auto-scaling signals.

Variant capacity defaults:
    mini_parwa   — 5 concurrent
    parwa        — 10 concurrent
    parwa_high   — 3 concurrent (premium, resource-heavy)

Thresholds:
    warning  — 70% utilization
    critical — 90% utilization
    full     — 95% utilization

Parent: Week 10 Day 3
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.logger import get_logger

logger = get_logger("capacity_monitor")


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass(order=True)
class QueueItem:
    """An item waiting in the capacity queue."""
    priority: int
    enqueued_at: float = field(default_factory=time.time)
    ticket_id: str = ""
    company_id: str = ""
    variant: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CapacityAlert:
    """A capacity threshold alert."""
    level: str  # warning, critical, full
    company_id: str
    variant: str
    message: str
    percentage: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


@dataclass
class UtilizationSnapshot:
    """A single utilization data point."""
    timestamp: float
    used: int
    total: int
    percentage: float


# ══════════════════════════════════════════════════════════════════
# DEFAULTS
# ══════════════════════════════════════════════════════════════════

DEFAULT_MAX_CONCURRENT: Dict[str, int] = {
    "mini_parwa": 5,
    "parwa": 10,
    "parwa_high": 3,
}

THRESHOLD_WARNING = 0.70
THRESHOLD_CRITICAL = 0.90
THRESHOLD_FULL = 0.95

ALL_VARIANTS = ("mini_parwa", "parwa", "parwa_high")


# ══════════════════════════════════════════════════════════════════
# CAPACITY MONITOR
# ══════════════════════════════════════════════════════════════════


class CapacityMonitor:
    """Track concurrent workflow executions per company/variant.

    Features:
    - Per-variant slot management
    - FIFO queue with priority ordering
    - Threshold-based alerts (70% warning, 90% critical, 95% full)
    - Historical utilization metrics
    - Overflow detection
    - Thread-safe via reentrant lock

    Usage::

        monitor = CapacityMonitor()
        if monitor.acquire_slot("co_1", "parwa", "tkt_1"):
            try:
                # ... do work ...
            finally:
                monitor.release_slot("co_1", "parwa", "tkt_1")
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Active slots: {company_id: {variant: {ticket_id: metadata}}}
        self._active_slots: Dict[
            str, Dict[str, Dict[str, Any]]
        ] = defaultdict(lambda: defaultdict(dict))
        # Company-specific limits: {company_id: {variant: max}}
        self._limits: Dict[str, Dict[str, int]] = {}
        # Queues: {company_id: {variant: deque[QueueItem]}}
        self._queues: Dict[
            str, Dict[str, deque]
        ] = defaultdict(lambda: defaultdict(deque))
        # Active alerts
        self._alerts: Dict[str, List[CapacityAlert]] = defaultdict(list)
        # Utilization history
        self._utilization: Dict[
            str, Dict[str, deque]
        ] = defaultdict(lambda: defaultdict(deque))
        self._utilization_max_points = 1000

    # ── Capacity Limits ────────────────────────────────────────

    def _get_max(self, company_id: str, variant: str) -> int:
        """Get max concurrent for company+variant.

        Uses company-specific override if set, else defaults.
        """
        company_limits = self._limits.get(company_id, {})
        if variant in company_limits:
            return company_limits[variant]
        return DEFAULT_MAX_CONCURRENT.get(variant, 10)

    def configure_limits(
        self,
        company_id: str,
        variant: str,
        max_concurrent: int,
    ) -> None:
        """Set custom capacity limits for a company+variant.

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant name.
            max_concurrent: Maximum concurrent executions.
        """
        if max_concurrent < 1:
            raise ValueError(
                f"max_concurrent must be >= 1, got {max_concurrent}"
            )
        with self._lock:
            if company_id not in self._limits:
                self._limits[company_id] = {}
            self._limits[company_id][variant] = max_concurrent
            logger.info(
                "capacity_limit_configured",
                company_id=company_id,
                variant=variant,
                max_concurrent=max_concurrent,
            )

    # ── Slot Acquisition ───────────────────────────────────────

    def acquire_slot(
        self,
        company_id: str,
        variant: str,
        ticket_id: str,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Acquire an execution slot.

        If capacity is available, grants a slot immediately.
        Otherwise, queues the request (FIFO with priority).

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant.
            ticket_id: Ticket identifier.
            priority: Higher = more urgent (default 0).
            metadata: Optional execution context.

        Returns:
            True if slot acquired, False if queued.
        """
        with self._lock:
            max_c = self._get_max(company_id, variant)
            active = self._active_slots[company_id][variant]
            current_used = len(active)

            if current_used < max_c:
                active[ticket_id] = metadata or {}
                self._record_utilization(
                    company_id, variant, current_used + 1, max_c
                )
                self._check_thresholds(
                    company_id, variant, current_used + 1, max_c
                )
                logger.info(
                    "slot_acquired",
                    company_id=company_id,
                    variant=variant,
                    ticket_id=ticket_id,
                    used=current_used + 1,
                    max=max_c,
                )
                return True
            else:
                # Queue the request
                item = QueueItem(
                    priority=priority,
                    ticket_id=ticket_id,
                    company_id=company_id,
                    variant=variant,
                    metadata=metadata or {},
                )
                self._queues[company_id][variant].append(item)
                self._check_thresholds(
                    company_id, variant, current_used, max_c
                )
                logger.info(
                    "slot_queued",
                    company_id=company_id,
                    variant=variant,
                    ticket_id=ticket_id,
                    queue_size=len(
                        self._queues[company_id][variant]
                    ),
                )
                return False

    # ── Slot Release ───────────────────────────────────────────

    def release_slot(
        self,
        company_id: str,
        variant: str,
        ticket_id: str,
    ) -> bool:
        """Release an execution slot.

        After releasing, processes the queue if items are waiting.

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant.
            ticket_id: Ticket identifier.

        Returns:
            True if slot was released, False if not found.
        """
        with self._lock:
            active = self._active_slots[company_id][variant]
            if ticket_id not in active:
                return False

            del active[ticket_id]
            max_c = self._get_max(company_id, variant)
            current_used = len(active)
            self._record_utilization(
                company_id, variant, current_used, max_c
            )
            self._clear_alerts_for_variant(company_id, variant)

            logger.info(
                "slot_released",
                company_id=company_id,
                variant=variant,
                ticket_id=ticket_id,
                remaining=current_used,
                max=max_c,
            )

            # Process queue
            self._process_queue_locked(company_id, variant)
            return True

    # ── Capacity Query ─────────────────────────────────────────

    def get_capacity(
        self,
        company_id: str,
        variant: str,
    ) -> Dict[str, Any]:
        """Get current capacity status for company+variant.

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant.

        Returns:
            Dict with used, total, available, percentage.
        """
        with self._lock:
            max_c = self._get_max(company_id, variant)
            used = len(
                self._active_slots[company_id][variant]
            )
            available = max(0, max_c - used)
            pct = (used / max_c * 100) if max_c > 0 else 0
            return {
                "used": used,
                "total": max_c,
                "available": available,
                "percentage": round(pct, 2),
            }

    # ── Queue Operations ───────────────────────────────────────

    def get_queue_position(
        self,
        company_id: str,
        variant: str,
        ticket_id: str,
    ) -> int:
        """Get position of a ticket in the queue (0-indexed).

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant.
            ticket_id: Ticket identifier.

        Returns:
            Queue position (0 = next), or -1 if not in queue.
        """
        with self._lock:
            q = self._queues[company_id][variant]
            for i, item in enumerate(q):
                if item.ticket_id == ticket_id:
                    return i
            return -1

    def get_queue_size(
        self,
        company_id: str,
        variant: str,
    ) -> int:
        """Get the number of items in queue for company+variant.

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant.

        Returns:
            Queue size.
        """
        with self._lock:
            return len(self._queues[company_id][variant])

    def process_queue(
        self,
        company_id: str,
        variant: str,
    ) -> List[str]:
        """Process queued items if capacity available.

        Dequeues and activates items in priority order (FIFO
        within same priority).

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant.

        Returns:
            List of ticket_ids that were dequeued and activated.
        """
        with self._lock:
            return self._process_queue_locked(company_id, variant)

    def _process_queue_locked(
        self,
        company_id: str,
        variant: str,
    ) -> List[str]:
        """Internal queue processor (must be called with lock held).

        Returns:
            List of ticket_ids that were dequeued and activated.
        """
        activated = []
        max_c = self._get_max(company_id, variant)
        active = self._active_slots[company_id][variant]
        q = self._queues[company_id][variant]

        while q and len(active) < max_c:
            # Sort by priority (higher first), then by enqueue time
            sorted_q = sorted(q, key=lambda x: (-x.priority, x.enqueued_at))
            item = sorted_q[0]

            # Remove from queue
            q.remove(item)
            active[item.ticket_id] = item.metadata

            activated.append(item.ticket_id)
            self._record_utilization(
                company_id, variant, len(active), max_c
            )
            self._check_thresholds(
                company_id, variant, len(active), max_c
            )
            logger.info(
                "queue_item_activated",
                company_id=company_id,
                variant=variant,
                ticket_id=item.ticket_id,
                priority=item.priority,
            )

        return activated

    # ── Alerting ───────────────────────────────────────────────

    def _check_thresholds(
        self,
        company_id: str,
        variant: str,
        used: int,
        max_c: int,
    ) -> None:
        """Check utilization thresholds and generate alerts."""
        if max_c == 0:
            return
        pct = used / max_c

        alert = None
        if pct >= THRESHOLD_FULL:
            level = "full"
            alert = CapacityAlert(
                level=level,
                company_id=company_id,
                variant=variant,
                message=(
                    f"Capacity FULL ({used}/{max_c}, "
                    f"{pct * 100:.0f}%) for {variant}"
                ),
                percentage=round(pct * 100, 2),
            )
        elif pct >= THRESHOLD_CRITICAL:
            level = "critical"
            alert = CapacityAlert(
                level=level,
                company_id=company_id,
                variant=variant,
                message=(
                    f"Capacity CRITICAL ({used}/{max_c}, "
                    f"{pct * 100:.0f}%) for {variant}"
                ),
                percentage=round(pct * 100, 2),
            )
        elif pct >= THRESHOLD_WARNING:
            level = "warning"
            alert = CapacityAlert(
                level=level,
                company_id=company_id,
                variant=variant,
                message=(
                    f"Capacity WARNING ({used}/{max_c}, "
                    f"{pct * 100:.0f}%) for {variant}"
                ),
                percentage=round(pct * 100, 2),
            )

        if alert:
            # Deduplicate: don't add if same level+variant exists
            existing = [
                a for a in self._alerts[company_id]
                if a.variant == variant and a.level == alert.level
            ]
            if not existing:
                self._alerts[company_id].append(alert)
                logger.warning(
                    "capacity_alert",
                    level=alert.level,
                    company_id=company_id,
                    variant=variant,
                    percentage=alert.percentage,
                )

    def _clear_alerts_for_variant(
        self,
        company_id: str,
        variant: str,
    ) -> None:
        """Clear alerts for a variant when utilization drops."""
        self._alerts[company_id] = [
            a for a in self._alerts.get(company_id, [])
            if a.variant != variant
        ]

    def get_alerts(self, company_id: str) -> List[Dict[str, Any]]:
        """Get active capacity alerts for a company.

        Args:
            company_id: Tenant identifier.

        Returns:
            List of alert dictionaries.
        """
        with self._lock:
            alerts = self._alerts.get(company_id, [])
            return [
                {
                    "level": a.level,
                    "variant": a.variant,
                    "message": a.message,
                    "percentage": a.percentage,
                    "timestamp": a.timestamp,
                }
                for a in alerts
            ]

    # ── Utilization History ────────────────────────────────────

    def _record_utilization(
        self,
        company_id: str,
        variant: str,
        used: int,
        total: int,
    ) -> None:
        """Record a utilization snapshot."""
        pct = (used / total * 100) if total > 0 else 0
        snapshot = UtilizationSnapshot(
            timestamp=time.time(),
            used=used,
            total=total,
            percentage=round(pct, 2),
        )
        buf = self._utilization[company_id][variant]
        buf.append(snapshot)
        # Trim to max points
        while len(buf) > self._utilization_max_points:
            buf.popleft()

    def get_utilization_history(
        self,
        company_id: str,
        variant: str,
        window_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get utilization time series data.

        Args:
            company_id: Tenant identifier.
            variant: PARWA variant.
            window_seconds: Optional time window. None = all data.

        Returns:
            List of utilization snapshot dicts.
        """
        with self._lock:
            buf = self._utilization[company_id][variant]
            cutoff = (
                time.time() - window_seconds
                if window_seconds
                else 0
            )
            return [
                {
                    "timestamp": s.timestamp,
                    "used": s.used,
                    "total": s.total,
                    "percentage": s.percentage,
                }
                for s in buf
                if s.timestamp >= cutoff
            ]

    # ── Overflow Detection ─────────────────────────────────────

    def get_overflow_status(self, company_id: str) -> Dict[str, Any]:
        """Get overall capacity overflow status for a company.

        Checks all variants for capacity pressure.

        Args:
            company_id: Tenant identifier.

        Returns:
            Overflow status dictionary.
        """
        with self._lock:
            variants_status = {}
            has_overflow = False
            total_queued = 0

            for variant in ALL_VARIANTS:
                cap = self.get_capacity(company_id, variant)
                queue_size = self.get_queue_size(
                    company_id, variant
                )
                total_queued += queue_size

                is_overflow = (
                    cap["percentage"] >= THRESHOLD_WARNING * 100
                    or queue_size > 0
                )
                if is_overflow:
                    has_overflow = True

                variants_status[variant] = {
                    "utilization_percentage": cap["percentage"],
                    "queue_size": queue_size,
                    "is_overflow": is_overflow,
                    "max_concurrent": cap["total"],
                }

            # Auto-scaling signal
            scaling_suggestion = None
            if has_overflow:
                high_util_variants = [
                    v for v, s in variants_status.items()
                    if s["utilization_percentage"]
                    >= THRESHOLD_CRITICAL * 100
                ]
                if high_util_variants:
                    scaling_suggestion = {
                        "action": "increase_capacity",
                        "variants": high_util_variants,
                        "reason": (
                            f"Variants {high_util_variants} "
                            f"at or above {THRESHOLD_CRITICAL * 100:.0f}% "
                            f"utilization."
                        ),
                    }

            return {
                "company_id": company_id,
                "has_overflow": has_overflow,
                "total_queued": total_queued,
                "variants": variants_status,
                "scaling_suggestion": scaling_suggestion,
            }

    # ── Cleanup ────────────────────────────────────────────────

    def clear_company(self, company_id: str) -> None:
        """Clear all capacity data for a company.

        Args:
            company_id: Tenant identifier.
        """
        with self._lock:
            self._active_slots.pop(company_id, None)
            self._queues.pop(company_id, None)
            self._alerts.pop(company_id, None)
            self._utilization.pop(company_id, None)
            self._limits.pop(company_id, None)

    def reset(self) -> None:
        """Clear all capacity data (for testing)."""
        with self._lock:
            self._active_slots.clear()
            self._queues.clear()
            self._alerts.clear()
            self._utilization.clear()
            # Keep _limits as they are configuration
