"""
Shared GSD Module — Reusable GSD utilities for PARWA (F-053)

Provides:
- GSD state transition validator (re-exports from gsd_engine with helpers)
- GSD lifecycle manager (track state transitions over time)
- GSD analytics (time in each state, transition frequency heatmap,
  bottleneck detection)
- GSD recovery actions (suggest recovery when stuck in a state)
- GSD event emitter (transition events for WebSocket/Socket.io)

Parent: Week 10 Day 3
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("shared_gsd")


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class TransitionLogEntry:
    """A single recorded state transition."""

    company_id: str
    ticket_id: str
    from_state: str
    to_state: str
    timestamp: float  # epoch seconds
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateDuration:
    """Duration spent in a specific state."""

    state: str
    duration_seconds: float
    entry_timestamp: Optional[float] = None
    exit_timestamp: Optional[float] = None


@dataclass
class RecoverySuggestion:
    """A recovery action suggestion when stuck."""

    action: str
    reason: str
    priority: str  # high, medium, low
    target_state: Optional[str] = None


@dataclass
class CapacityAlert:
    """Capacity alert for GSD tracking."""

    level: str  # warning, critical, full
    company_id: str
    variant: str
    message: str
    percentage: float
    timestamp: float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════
# SHARED GSD MANAGER
# ══════════════════════════════════════════════════════════════════


class SharedGSDManager:
    """Shared GSD utilities for the PARWA platform.

    Provides GSD state validation, lifecycle tracking, analytics,
    recovery suggestions, and transition event emission.

    All methods are synchronous for simplicity and performance.
    Company-scoped data is isolated per BC-001.
    """

    # Stuck detection thresholds (seconds)
    STUCK_THRESHOLD_SECONDS = 300.0  # 5 minutes
    CRITICAL_STUCK_THRESHOLD_SECONDS = 600.0  # 10 minutes

    def __init__(self) -> None:
        self._transition_history: Dict[str, Dict[str, List[TransitionLogEntry]]] = (
            defaultdict(lambda: defaultdict(list))
        )
        self._current_states: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._transition_counts: Dict[str, Dict[Tuple[str, str], int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._state_entry_times: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._event_listeners: List = []

    # ── Transition Validation ──────────────────────────────────

    @staticmethod
    def get_valid_transitions(
        current_state: str,
        variant: Optional[str] = None,
    ) -> List[str]:
        """Return list of valid target states for a current state.

        Args:
            current_state: Current GSD state string.
            variant: PARWA variant (mini_parwa, parwa, high_parwa).

        Returns:
            Sorted list of valid target state strings.
        """
        from app.core.gsd_engine import (
            ESCALATION_ELIGIBLE_STATES,
            FULL_TRANSITION_TABLE,
            MINI_TRANSITION_TABLE,
        )

        if variant == "mini_parwa":
            table = MINI_TRANSITION_TABLE
        else:
            table = FULL_TRANSITION_TABLE

        allowed = set(table.get(current_state, set()))

        if variant != "mini_parwa":
            if current_state in ESCALATION_ELIGIBLE_STATES:
                allowed.add("escalate")

        return sorted(allowed)

    @staticmethod
    def get_transition_reason(
        current_state: str,
        target_state: str,
    ) -> Dict[str, Any]:
        """Explain why a transition is valid or invalid.

        Args:
            current_state: Current GSD state string.
            target_state: Target GSD state string.

        Returns:
            Dictionary with valid flag and explanation.
        """
        valid_targets = SharedGSDManager.get_valid_transitions(current_state)
        is_valid = target_state in valid_targets

        if is_valid:
            return {
                "valid": True,
                "reason": (
                    f"Transition {current_state} -> {target_state} "
                    "is permitted by the GSD state machine."
                ),
            }
        else:
            suggestion = ""
            if valid_targets:
                suggestion = (
                    f" Valid targets from {current_state}: "
                    f"{', '.join(valid_targets)}."
                )
            return {
                "valid": False,
                "reason": (
                    f"Transition {current_state} -> {target_state} "
                    "is not permitted." + suggestion
                ),
            }

    # ── Transition Recording ───────────────────────────────────

    def record_transition(
        self,
        company_id: str,
        ticket_id: str,
        from_state: str,
        to_state: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a state transition for a ticket.

        Args:
            company_id: Tenant identifier (BC-001).
            ticket_id: Ticket identifier.
            from_state: Previous GSD state.
            to_state: New GSD state.
            metadata: Optional context for the transition.
        """
        now = time.time()
        entry = TransitionLogEntry(
            company_id=company_id,
            ticket_id=ticket_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=now,
            metadata=metadata or {},
        )
        self._transition_history[company_id][ticket_id].append(entry)

        # Track transition counts for heatmap
        key = (from_state, to_state)
        self._transition_counts[company_id][key] += 1

        # Track state entry times
        self._state_entry_times[company_id][ticket_id][to_state] = now

        # Update current state
        self._current_states[company_id][ticket_id] = {
            "state": to_state,
            "entered_at": now,
        }

        logger.info(
            "gsd_transition_recorded",
            company_id=company_id,
            ticket_id=ticket_id,
            from_state=from_state,
            to_state=to_state,
        )

        # Emit to event listeners
        self._emit_transition_event(entry)

    # ── History Retrieval ──────────────────────────────────────

    def get_transition_history(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[Dict[str, Any]]:
        """Get the timeline of transitions for a ticket.

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket identifier.

        Returns:
            List of transition dictionaries sorted by timestamp.
        """
        entries = self._transition_history.get(company_id, {}).get(ticket_id, [])
        return [
            {
                "from_state": e.from_state,
                "to_state": e.to_state,
                "timestamp": e.timestamp,
                "metadata": e.metadata,
            }
            for e in entries
        ]

    # ── State Duration ─────────────────────────────────────────

    def get_state_duration(
        self,
        company_id: str,
        ticket_id: str,
        state: str,
    ) -> float:
        """Get time spent in a specific state for a ticket.

        Calculates duration from entry time to either exit time
        (next transition) or now (if currently in that state).

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket identifier.
            state: GSD state to measure.

        Returns:
            Duration in seconds. Returns 0.0 if state was never
            entered for this ticket.
        """
        history = self._transition_history.get(company_id, {}).get(ticket_id, [])
        if not history:
            return 0.0

        # Find entries where the state was entered (to_state == state)
        entry_times = []
        for entry in history:
            if entry.to_state == state:
                entry_times.append(entry.timestamp)

        if not entry_times:
            return 0.0

        # Find exit times (from_state == state for a subsequent entry)
        exit_times = []
        for entry in history:
            if entry.from_state == state and entry.timestamp in entry_times:
                continue
            if entry.from_state == state:
                exit_times.append(entry.timestamp)

        # For the most recent entry, check if still in that state
        current = self._current_states.get(company_id, {}).get(ticket_id, {})
        total = 0.0
        for i, entry_t in enumerate(entry_times):
            if i < len(exit_times):
                total += exit_times[i] - entry_t
            elif current.get("state") == state:
                # Still in this state
                total += time.time() - entry_t

        return total

    # ── Analytics ──────────────────────────────────────────────

    def get_analytics(self, company_id: str) -> Dict[str, Any]:
        """Get GSD analytics for a company.

        Includes state distribution, average durations, bottleneck
        detection, and transition frequency summary.

        Args:
            company_id: Tenant identifier.

        Returns:
            Analytics dictionary.
        """
        all_tickets = self._transition_history.get(company_id, {})
        state_counts: Dict[str, int] = defaultdict(int)
        state_durations: Dict[str, List[float]] = defaultdict(list)
        bottleneck_states: List[Dict[str, Any]] = []

        for ticket_id, entries in all_tickets.items():
            for entry in entries:
                state_counts[entry.to_state] += 1
                dur = self.get_state_duration(company_id, ticket_id, entry.to_state)
                if dur > 0:
                    state_durations[entry.to_state].append(dur)

        # Calculate average durations
        avg_durations = {}
        for state, durations in state_durations.items():
            avg_durations[state] = sum(durations) / len(durations)

        # Bottleneck detection: states with avg duration > threshold
        for state, avg_dur in avg_durations.items():
            if avg_dur > self.STUCK_THRESHOLD_SECONDS:
                level = "critical"
                if avg_dur < self.CRITICAL_STUCK_THRESHOLD_SECONDS:
                    level = "warning"
                bottleneck_states.append(
                    {
                        "state": state,
                        "avg_duration_seconds": round(avg_dur, 2),
                        "level": level,
                        "sample_count": len(state_durations[state]),
                    }
                )

        # Sort bottlenecks by duration descending
        bottleneck_states.sort(key=lambda x: x["avg_duration_seconds"], reverse=True)

        total_transitions = sum(len(entries) for entries in all_tickets.values())

        return {
            "company_id": company_id,
            "total_tickets": len(all_tickets),
            "total_transitions": total_transitions,
            "state_distribution": dict(state_counts),
            "average_duration_seconds": avg_durations,
            "bottleneck_states": bottleneck_states,
            "transition_frequency": dict(self._transition_counts.get(company_id, {})),
        }

    # ── Recovery Suggestions ───────────────────────────────────

    def suggest_recovery(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[Dict[str, Any]]:
        """Suggest recovery actions when a ticket appears stuck.

        Detects stuck states and recommends actions to unblock.

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket identifier.

        Returns:
            List of recovery suggestion dictionaries.
        """
        suggestions: List[Dict[str, Any]] = []
        current = self._current_states.get(company_id, {}).get(ticket_id)
        if not current:
            return suggestions

        state = current.get("state", "")
        entered_at = current.get("entered_at", 0)
        if not entered_at:
            return suggestions

        duration = time.time() - entered_at

        if duration > self.CRITICAL_STUCK_THRESHOLD_SECONDS:
            suggestions.append(
                {
                    "action": "escalate_to_human",
                    "reason": (
                        f"Ticket stuck in '{state}' for "
                        f"{duration:.0f}s (> "
                        f"{self.CRITICAL_STUCK_THRESHOLD_SECONDS:.0f}s). "
                        "Immediate human review recommended."
                    ),
                    "priority": "high",
                    "target_state": "human_handoff",
                }
            )
            suggestions.append(
                {
                    "action": "force_transition",
                    "reason": (
                        "Consider force-transitioning to 'closed' "
                        "if the issue has been resolved externally."
                    ),
                    "priority": "medium",
                    "target_state": "closed",
                }
            )
        elif duration > self.STUCK_THRESHOLD_SECONDS:
            suggestions.append(
                {
                    "action": "review_state",
                    "reason": (
                        f"Ticket in '{state}' for {duration:.0f}s. "
                        "Review may be needed."
                    ),
                    "priority": "medium",
                    "target_state": None,
                }
            )
            # Check valid transitions from current state
            valid = self.get_valid_transitions(state)
            if valid:
                suggestions.append(
                    {
                        "action": "suggest_transition",
                        "reason": (
                            f"Valid next states from '{state}': " f"{', '.join(valid)}"
                        ),
                        "priority": "low",
                        "target_state": valid[0] if valid else None,
                    }
                )

        # Check for diagnosis loops
        history = self._transition_history.get(company_id, {}).get(ticket_id, [])
        diagnosis_count = sum(1 for e in history if e.to_state == "diagnosis")
        if diagnosis_count > 3:
            suggestions.append(
                {
                    "action": "escalate_diagnosis_loop",
                    "reason": (
                        f"DIAGNOSIS entered {diagnosis_count} times. "
                        "Auto-escalation recommended."
                    ),
                    "priority": "high",
                    "target_state": "escalate",
                }
            )

        if not suggestions:
            suggestions.append(
                {
                    "action": "no_action_needed",
                    "reason": "Ticket is progressing normally.",
                    "priority": "low",
                    "target_state": None,
                }
            )

        return suggestions

    # ── Transition Heatmap ─────────────────────────────────────

    def get_transition_heatmap(
        self,
        company_id: str,
    ) -> Dict[str, Dict[str, int]]:
        """Get a matrix of from->to transition counts.

        Args:
            company_id: Tenant identifier.

        Returns:
            Nested dict: {from_state: {to_state: count}}.
        """
        counts = self._transition_counts.get(company_id, {})
        heatmap: Dict[str, Dict[str, int]] = defaultdict(dict)
        for (from_s, to_s), count in counts.items():
            heatmap[from_s][to_s] = count
        return dict(heatmap)

    # ── Event Emission ─────────────────────────────────────────

    def add_event_listener(self, callback: Any) -> None:
        """Add a listener for transition events.

        Callback signature: callback(entry: TransitionLogEntry)

        Args:
            callback: Callable to invoke on each transition.
        """
        self._event_listeners.append(callback)

    def remove_event_listener(self, callback: Any) -> None:
        """Remove a previously registered listener.

        Args:
            callback: The callable to remove.
        """
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    def _emit_transition_event(
        self,
        entry: TransitionLogEntry,
    ) -> None:
        """Emit transition event to all registered listeners.

        Args:
            entry: The transition log entry to emit.
        """
        for listener in self._event_listeners:
            try:
                listener(entry)
            except Exception as exc:
                logger.error(
                    "gsd_event_listener_error",
                    error=str(exc),
                    listener=getattr(listener, "__name__", "unknown"),
                )

    # ── Lifecycle Helpers ──────────────────────────────────────

    def get_current_state(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[str]:
        """Get the current GSD state for a ticket.

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket identifier.

        Returns:
            Current state string or None if no state tracked.
        """
        current = self._current_states.get(company_id, {}).get(ticket_id)
        if current:
            return current.get("state")
        return None

    def clear_ticket_data(
        self,
        company_id: str,
        ticket_id: str,
    ) -> None:
        """Clear all tracked data for a specific ticket.

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket identifier.
        """
        self._transition_history[company_id].pop(ticket_id, None)
        self._current_states[company_id].pop(ticket_id, None)
        if ticket_id in self._state_entry_times.get(company_id, {}):
            self._state_entry_times[company_id].pop(ticket_id, None)

        # BUG FIX: Rebuild _transition_counts from remaining history
        # for this company_id, since _transition_counts is keyed by
        # (company_id, (from_state, to_state)) — not by ticket_id —
        # the deleted ticket's transitions would otherwise linger.
        self._transition_counts[company_id] = defaultdict(int)
        remaining = self._transition_history.get(company_id, {})
        for tid, entries in remaining.items():
            for entry in entries:
                key = (entry.from_state, entry.to_state)
                self._transition_counts[company_id][key] += 1

    def clear_company_data(self, company_id: str) -> None:
        """Clear all tracked data for a company.

        Args:
            company_id: Tenant identifier.
        """
        self._transition_history.pop(company_id, None)
        self._current_states.pop(company_id, None)
        self._transition_counts.pop(company_id, None)
        self._state_entry_times.pop(company_id, None)
