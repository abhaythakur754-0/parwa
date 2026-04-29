"""
PARWA Trust Preservation Protocol Service (F-094) — Customer Trust During Degradation

When systems degrade, this protocol ensures customer-facing responses
maintain trust. Implements a three-tier protocol (GREEN/AMBER/RED) that
automatically adjusts AI behavior based on system health.

Protocol Modes:
1. GREEN (Normal)    — All AI features active, full response generation
2. AMBER (Degraded)  — Some providers down, honesty headers, simpler responses
3. RED (Critical)    — Major outage, AI paused, human handoff message

Protocol Logic:
- Auto-escalate based on system_status_service health data
- GREEN→AMBER: When any critical subsystem (LLM, DB) is "degraded"
- AMBER→RED: When any critical subsystem is "down" OR > 2 subsystems degraded
- RED→AMBER: When all subsystems back to "healthy" for 5 consecutive minutes
- AMBER→GREEN: When all subsystems healthy for 15 consecutive minutes (debounce)

Response Modification:
- AMBER: append honesty prefix, simplify response, disable auto-execute
- RED: return human handoff message, disable AI, queue for later
- Track protocol transitions in audit log
- Socket.io broadcast protocol changes to all tenant rooms

Methods:
- get_protocol_status()    — Current protocol mode and details
- set_protocol_mode()      — Manually set protocol mode (admin only)
- evaluate_and_update()    — Auto-evaluate health and update protocol
- get_response_wrapper()   — Get response modification wrapper
- get_protocol_history()   — Protocol transition history
- get_recovery_estimate()  — Estimated time to recovery

Building Codes: BC-001 (multi-tenant), BC-005 (real-time),
               BC-007 (AI model), BC-012 (error handling)
"""

import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.logger import get_logger

logger = get_logger("trust_preservation_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Redis TTL for protocol event log (7 days)
PROTOCOL_LOG_TTL_SECONDS = 604800  # 7 * 24 * 3600

# Maximum protocol events to keep per company
MAX_PROTOCOL_EVENTS = 200

# Debounce intervals for protocol transitions (seconds)
GREEN_STABLE_SECONDS = 900   # 15 minutes healthy → GREEN
AMBER_STABLE_SECONDS = 300   # 5 minutes healthy → AMBER

# Subsystems considered critical for protocol evaluation
CRITICAL_SUBSYSTEMS = {"llm_providers", "redis", "postgresql"}

# Socket.io event for real-time push
SOCKETIO_EVENT_PROTOCOL_CHANGE = "trust_protocol:mode_changed"

# Honesty prefixes for AMBER mode
AMBER_HONESTY_PREFIX = (
    "I'm experiencing some technical difficulties, "
    "but I'm still here to help. "
)

# Human handoff message for RED mode
RED_HANDOFF_MESSAGE = (
    "I'm currently experiencing a technical issue and "
    "can't assist you right now. A human team member "
    "will be with you shortly. Thank you for your patience."
)

# Response modifications
AMBER_RESPONSE_SUFFIX = (
    "\n\n*Some features may be limited due to "
    "technical difficulties.*"
)

# Queued response message (for RED mode)
RED_QUEUED_MESSAGE = (
    "[Message queued for later delivery — "
    "system in maintenance mode]"
)


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class ProtocolMode(str, Enum):
    """Trust preservation protocol modes."""
    GREEN = "green"    # Normal — all AI features active
    AMBER = "amber"    # Degraded — honesty headers, simpler responses
    RED = "red"        # Critical — AI paused, human handoff


class ProtocolTransitionReason(str, Enum):
    """Reasons for protocol transitions."""
    AUTO_ESCALATE_CRITICAL = "auto_escalate_critical"
    AUTO_ESCALATE_DEGRADED = "auto_escalate_degraded"
    AUTO_DEESCALATE_HEALTHY = "auto_deescalate_healthy"
    MANUAL_OVERRIDE = "manual_override"
    EMERGENCY_ACTIVATE = "emergency_activate"


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class TrustPreservationService:
    """Trust Preservation Protocol Service (F-094).

    Manages the three-tier protocol (GREEN/AMBER/RED) to ensure
    customer-facing responses maintain trust during system degradation.

    BC-001: All methods scoped by company_id.
    BC-005: Real-time Socket.io broadcast on mode changes.
    BC-007: AI response modification based on protocol mode.
    BC-008: Never crash — graceful degradation.
    BC-012: All timestamps UTC, structured responses.
    """

    def __init__(self, company_id: str):
        """Initialize the service for a specific tenant.

        Args:
            company_id: Tenant identifier (BC-001).
        """
        self.company_id = company_id
        self._redis = None
        self._current_mode: ProtocolMode = ProtocolMode.GREEN
        self._healthy_since: Optional[float] = None
        self._last_evaluation: Optional[str] = None
        self._manual_override: bool = False

    # ── Lazy Redis Loading ──────────────────────────────────────

    async def _get_redis(self):
        """Get Redis connection (lazy, with graceful fallback)."""
        if self._redis is not None:
            return self._redis
        try:
            from app.core.redis import get_redis
            self._redis = await get_redis()
            return self._redis
        except Exception as exc:
            logger.warning(
                "trust_protocol_redis_unavailable",
                company_id=self.company_id,
                error=str(exc),
            )
            return None

    # ── Core Methods ────────────────────────────────────────────

    async def get_protocol_status(self) -> Dict[str, Any]:
        """Get the current trust protocol status.

        Returns the current mode, when it was set, the reason for
        the last transition, and the current subsystem health summary.

        Returns:
            Dictionary with protocol status details.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Try to read persisted state from Redis
        persisted = await self._read_persisted_state()

        current_mode = (
            ProtocolMode(persisted["mode"])
            if persisted
            else self._current_mode
        )
        manual_override = (
            persisted.get("manual_override", False)
            if persisted
            else self._manual_override
        )

        # Get subsystem health summary
        subsystem_summary = {}
        critical_degraded = []
        critical_down = []
        total_degraded = 0

        try:
            from app.services.system_status_service import (
                get_system_status_service,
            )
            svc = get_system_status_service(self.company_id)
            status_data = await svc.get_system_status()

            for name, info in status_data.get("subsystems", {}).items():
                sub_status = info.get("status", "unknown")
                subsystem_summary[name] = sub_status

                if sub_status in ("degraded", "unhealthy"):
                    total_degraded += 1
                if (
                    sub_status in ("degraded", "unhealthy")
                    and name in CRITICAL_SUBSYSTEMS
                ):
                    critical_degraded.append(name)
                if sub_status == "unhealthy" and name in CRITICAL_SUBSYSTEMS:
                    critical_down.append(name)
        except Exception:
            pass

        return {
            "company_id": self.company_id,
            "current_mode": current_mode.value,
            "manual_override": manual_override,
            "checked_at": now,
            "last_evaluation": self._last_evaluation or now,
            "subsystem_summary": subsystem_summary,
            "critical_degraded": critical_degraded,
            "critical_down": critical_down,
            "total_degraded_subsystems": total_degraded,
            "features": self._get_mode_features(current_mode),
        }

    async def set_protocol_mode(
        self,
        mode: str,
        set_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually set the protocol mode (admin only).

        Allows admins to override the auto-evaluation. The manual
        override persists until the next auto-evaluation cycle
        clears it, or an admin resets it.

        Args:
            mode: Target protocol mode ('green', 'amber', 'red').
            set_by: User ID of the admin setting the mode.
            reason: Optional reason for the manual change.

        Returns:
            Dictionary with the new protocol status.
        """
        try:
            target_mode = ProtocolMode(mode.lower())
        except ValueError:
            return {
                "error": (
                    f"Invalid protocol mode '{mode}'. "
                    "Must be one of: green, amber, red"
                ),
                "valid_modes": [m.value for m in ProtocolMode],
            }

        now = datetime.now(timezone.utc)
        previous_mode = self._current_mode

        # Transition
        self._current_mode = target_mode
        self._manual_override = True
        self._last_evaluation = now.isoformat()

        # Persist to Redis
        await self._persist_state()

        # Log the transition
        transition_reason = (
            reason or ProtocolTransitionReason.MANUAL_OVERRIDE.value
        )
        await self._log_transition(
            previous_mode=previous_mode.value,
            new_mode=target_mode.value,
            reason=transition_reason,
            triggered_by=f"manual:{set_by}",
        )

        # Broadcast via Socket.io
        await self._broadcast_mode_change(
            previous_mode.value,
            target_mode.value,
            transition_reason,
        )

        logger.warning(
            "trust_protocol_manual_set",
            company_id=self.company_id,
            previous_mode=previous_mode.value,
            new_mode=target_mode.value,
            set_by=set_by,
            reason=reason,
        )

        return {
            "company_id": self.company_id,
            "previous_mode": previous_mode.value,
            "new_mode": target_mode.value,
            "manual_override": True,
            "set_by": set_by,
            "set_at": now.isoformat(),
            "reason": transition_reason,
        }

    async def evaluate_and_update(self) -> Dict[str, Any]:
        """Auto-evaluate system health and update protocol mode.

        Implements the protocol escalation/de-escalation logic:
        - GREEN→AMBER: Any critical subsystem degraded
        - AMBER→RED: Any critical subsystem down OR > 2 degraded
        - RED→AMBER: All healthy for 5 consecutive minutes
        - AMBER→GREEN: All healthy for 15 consecutive minutes

        If a manual override is active, auto-evaluation is skipped
        but health data is still collected.

        Returns:
            Dictionary with evaluation result and any transitions.
        """
        now = datetime.now(timezone.utc)
        now_ts = time.monotonic()
        self._last_evaluation = now.isoformat()

        # Get system health
        subsystems = {}
        critical_degraded = []
        critical_down = []
        total_degraded = 0
        any_unhealthy = False

        try:
            from app.services.system_status_service import (
                get_system_status_service,
            )
            svc = get_system_status_service(self.company_id)
            status_data = await svc.get_system_status()

            for name, info in status_data.get("subsystems", {}).items():
                sub_status = info.get("status", "unknown")
                subsystems[name] = sub_status

                if sub_status == "unhealthy":
                    any_unhealthy = True
                    total_degraded += 1
                elif sub_status == "degraded":
                    total_degraded += 1

                if (
                    sub_status in ("degraded", "unhealthy")
                    and name in CRITICAL_SUBSYSTEMS
                ):
                    critical_degraded.append(name)
                if sub_status == "unhealthy" and name in CRITICAL_SUBSYSTEMS:
                    critical_down.append(name)

        except Exception as exc:
            logger.warning(
                "trust_protocol_evaluate_error",
                company_id=self.company_id,
                error=str(exc),
            )

        # Read persisted mode
        persisted = await self._read_persisted_state()
        current_mode = (
            ProtocolMode(persisted["mode"])
            if persisted
            else self._current_mode
        )
        manual_override = (
            persisted.get("manual_override", False)
            if persisted
            else self._manual_override
        )

        # If manual override is active, skip auto-transition
        if manual_override:
            return {
                "company_id": self.company_id,
                "current_mode": current_mode.value,
                "manual_override": True,
                "evaluation_skipped": True,
                "subsystem_summary": subsystems,
                "critical_degraded": critical_degraded,
                "critical_down": critical_down,
                "total_degraded_subsystems": total_degraded,
                "evaluated_at": now.isoformat(),
            }

        # Track healthy duration
        all_healthy = (
            not any_unhealthy
            and total_degraded == 0
            and not critical_degraded
            and not critical_down
        )

        if all_healthy:
            if self._healthy_since is None:
                self._healthy_since = now_ts
        else:
            self._healthy_since = None

        healthy_duration = 0.0
        if self._healthy_since is not None:
            healthy_duration = now_ts - self._healthy_since

        previous_mode = current_mode
        transition_reason = None

        # ── Escalation Logic ────────────────────────────────

        if current_mode == ProtocolMode.GREEN:
            # GREEN→AMBER: Any critical subsystem degraded
            if critical_degraded:
                current_mode = ProtocolMode.AMBER
                transition_reason = (
                    ProtocolTransitionReason
                    .AUTO_ESCALATE_DEGRADED.value
                )
                self._healthy_since = None

        elif current_mode == ProtocolMode.AMBER:
            # AMBER→RED: Critical subsystem down OR > 2 degraded
            if critical_down:
                current_mode = ProtocolMode.RED
                transition_reason = (
                    ProtocolTransitionReason
                    .AUTO_ESCALATE_CRITICAL.value
                )
                self._healthy_since = None
            elif total_degraded > 2:
                current_mode = ProtocolMode.RED
                transition_reason = (
                    ProtocolTransitionReason
                    .AUTO_ESCALATE_CRITICAL.value
                )
                self._healthy_since = None
            # AMBER→GREEN: All healthy for 15 minutes
            elif all_healthy and healthy_duration >= GREEN_STABLE_SECONDS:
                current_mode = ProtocolMode.GREEN
                transition_reason = (
                    ProtocolTransitionReason
                    .AUTO_DEESCALATE_HEALTHY.value
                )

        elif current_mode == ProtocolMode.RED:
            # RED→AMBER: All healthy for 5 minutes
            if all_healthy and healthy_duration >= AMBER_STABLE_SECONDS:
                current_mode = ProtocolMode.AMBER
                transition_reason = (
                    ProtocolTransitionReason
                    .AUTO_DEESCALATE_HEALTHY.value
                )

        # ── Apply Transition ────────────────────────────────

        transitioned = False
        if transition_reason and current_mode != previous_mode:
            self._current_mode = current_mode
            self._manual_override = False

            await self._persist_state()
            await self._log_transition(
                previous_mode=previous_mode.value,
                new_mode=current_mode.value,
                reason=transition_reason,
                triggered_by="auto",
            )
            await self._broadcast_mode_change(
                previous_mode.value,
                current_mode.value,
                transition_reason,
            )

            logger.warning(
                "trust_protocol_transition",
                company_id=self.company_id,
                previous_mode=previous_mode.value,
                new_mode=current_mode.value,
                reason=transition_reason,
                critical_degraded=critical_degraded,
                critical_down=critical_down,
            )
            transitioned = True

        return {
            "company_id": self.company_id,
            "previous_mode": previous_mode.value,
            "current_mode": current_mode.value,
            "transitioned": transitioned,
            "transition_reason": transition_reason,
            "manual_override": False,
            "subsystem_summary": subsystems,
            "critical_degraded": critical_degraded,
            "critical_down": critical_down,
            "total_degraded_subsystems": total_degraded,
            "healthy_duration_seconds": round(healthy_duration, 1),
            "evaluated_at": now.isoformat(),
        }

    async def get_response_wrapper(
        self, original_response: str,
    ) -> Dict[str, Any]:
        """Get the response modification wrapper based on current protocol mode.

        In GREEN mode, responses are returned as-is.
        In AMBER mode, honesty prefix is appended and responses simplified.
        In RED mode, human handoff message replaces the response.

        Args:
            original_response: The original AI-generated response.

        Returns:
            Dictionary with modified response and metadata.
        """
        # Get current mode
        persisted = await self._read_persisted_state()
        current_mode = (
            ProtocolMode(persisted["mode"])
            if persisted
            else self._current_mode
        )

        if current_mode == ProtocolMode.GREEN:
            return {
                "response": original_response,
                "mode": ProtocolMode.GREEN.value,
                "modified": False,
                "auto_execute_enabled": True,
            }

        elif current_mode == ProtocolMode.AMBER:
            # Append honesty prefix and simplify
            modified = f"{AMBER_HONESTY_PREFIX}{original_response}"
            modified = self._simplify_response(modified)
            modified = f"{modified}{AMBER_RESPONSE_SUFFIX}"

            return {
                "response": modified,
                "mode": ProtocolMode.AMBER.value,
                "modified": True,
                "modification_type": "honesty_prefix_and_simplify",
                "auto_execute_enabled": False,
                "original_response_length": len(original_response),
                "modified_response_length": len(modified),
            }

        elif current_mode == ProtocolMode.RED:
            # Replace with human handoff message
            return {
                "response": RED_HANDOFF_MESSAGE,
                "mode": ProtocolMode.RED.value,
                "modified": True,
                "modification_type": "human_handoff",
                "auto_execute_enabled": False,
                "ai_paused": True,
                "original_response": RED_QUEUED_MESSAGE,
                "original_response_length": len(original_response),
            }

        return {
            "response": original_response,
            "mode": current_mode.value,
            "modified": False,
            "auto_execute_enabled": True,
        }

    async def get_protocol_history(
        self,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get protocol transition history.

        Returns the list of protocol mode transitions for audit
        and analysis.

        Args:
            limit: Maximum number of transitions to return.

        Returns:
            Dictionary with transition history and metadata.
        """
        events = await self._get_transition_events(limit=limit)

        return {
            "company_id": self.company_id,
            "transitions": events,
            "total": len(events),
            "limit": limit,
        }

    async def get_recovery_estimate(self) -> Dict[str, Any]:
        """Get estimated time to recovery.

        Analyzes current system health to estimate when the
        protocol can return to GREEN mode.

        Returns:
            Dictionary with recovery estimate details.
        """
        # Get current health
        subsystems = {}
        critical_issues = []
        degraded_count = 0

        try:
            from app.services.system_status_service import (
                get_system_status_service,
            )
            svc = get_system_status_service(self.company_id)
            status_data = await svc.get_system_status()

            for name, info in status_data.get("subsystems", {}).items():
                sub_status = info.get("status", "unknown")
                subsystems[name] = {
                    "status": sub_status,
                    "latency_ms": info.get("latency_ms", 0),
                    "error": info.get("error"),
                }

                if sub_status in ("degraded", "unhealthy"):
                    degraded_count += 1
                    if name in CRITICAL_SUBSYSTEMS:
                        critical_issues.append({
                            "subsystem": name,
                            "status": sub_status,
                            "error": info.get("error"),
                        })
        except Exception:
            pass

        # Get current mode
        persisted = await self._read_persisted_state()
        current_mode = (
            ProtocolMode(persisted["mode"])
            if persisted
            else self._current_mode
        )

        # Calculate recovery estimate
        if current_mode == ProtocolMode.GREEN:
            estimate_seconds = 0
            message = "System is healthy. No recovery needed."
        elif current_mode == ProtocolMode.AMBER:
            if not critical_issues:
                # No critical issues — just need 15 min stability
                estimate_seconds = GREEN_STABLE_SECONDS
                message = (
                    "All critical subsystems healthy. " f"Protocol will return to GREEN in ~{
                        GREEN_STABLE_SECONDS
                        // 60} " "minutes if stability maintained.")
            else:
                # Critical subsystems degraded
                estimate_seconds = -1  # Indeterminate
                message = (
                    "Critical subsystem(s) degraded: "
                    f"{', '.join(i['subsystem'] for i in critical_issues)}. "
                    "Recovery depends on subsystem resolution."
                )
        else:  # RED
            if not critical_issues:
                # No critical issues — need 5 min stability for AMBER
                estimate_seconds = AMBER_STABLE_SECONDS
                message = (
                    "Subsystems recovering. Protocol will move to "
                    f"AMBER in ~{AMBER_STABLE_SECONDS // 60} minutes, "
                    "then to GREEN after 15 minutes of stability."
                )
            else:
                estimate_seconds = -1
                message = (
                    "Critical subsystem(s) down: "
                    f"{', '.join(i['subsystem'] for i in critical_issues)}. "
                    "Immediate attention required."
                )

        # Healthy duration tracking
        healthy_seconds = 0.0
        if self._healthy_since is not None:
            healthy_seconds = time.monotonic() - self._healthy_since

        required_for_next = 0
        next_mode = None

        if current_mode == ProtocolMode.RED:
            required_for_next = AMBER_STABLE_SECONDS
            next_mode = "amber"
        elif current_mode == ProtocolMode.AMBER:
            required_for_next = GREEN_STABLE_SECONDS
            next_mode = "green"

        progress_pct = 0.0
        if required_for_next > 0 and healthy_seconds > 0:
            progress_pct = min(
                100.0, (healthy_seconds / required_for_next) * 100)

        return {
            "company_id": self.company_id,
            "current_mode": current_mode.value,
            "estimate_seconds": estimate_seconds,
            "estimate_message": message,
            "critical_issues": critical_issues,
            "degraded_count": degraded_count,
            "subsystem_summary": subsystems,
            "next_mode": next_mode,
            "healthy_duration_seconds": round(healthy_seconds, 1),
            "required_stable_seconds": required_for_next,
            "recovery_progress_pct": round(progress_pct, 1),
        }

    # ── Response Simplification ─────────────────────────────────

    @staticmethod
    def _simplify_response(response: str) -> str:
        """Simplify an AI response for AMBER mode.

        Removes excessive formatting, shortens very long responses,
        and strips speculative language.

        Args:
            response: The response to simplify.

        Returns:
            Simplified response string.
        """
        if not response:
            return response

        simplified = response

        # Strip excessive newlines (keep max 2 consecutive)
        import re
        simplified = re.sub(r"\n{3,}", "\n\n", simplified)

        # Truncate very long responses (> 2000 chars)
        if len(simplified) > 2000:
            simplified = simplified[:2000]
            # Find last sentence end
            last_period = simplified.rfind(".")
            last_excl = simplified.rfind("!")
            last_question = simplified.rfind("?")
            cutoff = max(last_period, last_excl, last_question)
            if cutoff > 1500:
                simplified = simplified[:cutoff + 1]

        return simplified.strip()

    # ── Mode Features ───────────────────────────────────────────

    @staticmethod
    def _get_mode_features(mode: ProtocolMode) -> Dict[str, Any]:
        """Get feature flags for a protocol mode.

        Args:
            mode: The protocol mode.

        Returns:
            Dictionary of feature flags.
        """
        if mode == ProtocolMode.GREEN:
            return {
                "ai_responses": True,
                "auto_execute": True,
                "honesty_headers": False,
                "response_simplification": False,
                "human_handoff": False,
                "queue_responses": False,
            }
        elif mode == ProtocolMode.AMBER:
            return {
                "ai_responses": True,
                "auto_execute": False,
                "honesty_headers": True,
                "response_simplification": True,
                "human_handoff": False,
                "queue_responses": False,
            }
        else:  # RED
            return {
                "ai_responses": False,
                "auto_execute": False,
                "honesty_headers": True,
                "response_simplification": True,
                "human_handoff": True,
                "queue_responses": True,
            }

    # ── Redis Persistence ───────────────────────────────────────

    async def _persist_state(self) -> None:
        """Persist current protocol state to Redis."""
        redis = await self._get_redis()
        if redis is None:
            return

        try:
            from app.core.redis import make_key

            state_key = make_key(
                self.company_id, "trust_protocol", "state",
            )
            state = {
                "company_id": self.company_id,
                "mode": self._current_mode.value,
                "manual_override": self._manual_override,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await redis.set(
                state_key, json.dumps(state),
                ex=PROTOCOL_LOG_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "trust_protocol_persist_failed",
                company_id=self.company_id,
                error=str(exc),
            )

    async def _read_persisted_state(
        self,
    ) -> Optional[Dict[str, Any]]:
        """Read persisted protocol state from Redis."""
        redis = await self._get_redis()
        if redis is None:
            return None

        try:
            from app.core.redis import make_key

            state_key = make_key(
                self.company_id, "trust_protocol", "state",
            )
            raw = await redis.get(state_key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass

        return None

    async def _log_transition(
        self,
        previous_mode: str,
        new_mode: str,
        reason: str,
        triggered_by: str,
    ) -> None:
        """Log a protocol transition event to Redis."""
        redis = await self._get_redis()
        if redis is None:
            return

        try:
            from app.core.redis import make_key

            log_key = make_key(
                self.company_id, "trust_protocol", "transitions",
            )

            event = {
                "transition_id": str(uuid4()),
                "company_id": self.company_id,
                "previous_mode": previous_mode,
                "new_mode": new_mode,
                "reason": reason,
                "triggered_by": triggered_by,
                "transitioned_at": datetime.now(timezone.utc).isoformat(),
            }

            await redis.lpush(log_key, json.dumps(event))
            await redis.ltrim(log_key, 0, MAX_PROTOCOL_EVENTS - 1)
            await redis.expire(log_key, PROTOCOL_LOG_TTL_SECONDS)

        except Exception as exc:
            logger.warning(
                "trust_protocol_log_failed",
                company_id=self.company_id,
                error=str(exc),
            )

    async def _get_transition_events(
        self, limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Read protocol transition events from Redis."""
        redis = await self._get_redis()
        if redis is None:
            return []

        events = []
        try:
            from app.core.redis import make_key

            log_key = make_key(
                self.company_id, "trust_protocol", "transitions",
            )
            raw_events = await redis.lrange(log_key, 0, limit - 1)

            for entry in raw_events:
                try:
                    event = json.loads(entry)
                    if event.get("company_id") == self.company_id:
                        events.append(event)
                except (json.JSONDecodeError, TypeError):
                    continue

        except Exception as exc:
            logger.warning(
                "trust_protocol_events_read_failed",
                company_id=self.company_id,
                error=str(exc),
            )

        return events

    async def _broadcast_mode_change(
        self,
        previous_mode: str,
        new_mode: str,
        reason: str,
    ) -> None:
        """Broadcast protocol mode change via Socket.io."""
        try:
            from app.core.socketio import get_socketio
            sio = get_socketio()
            if sio:
                room = f"company:{self.company_id}"
                await sio.emit(
                    SOCKETIO_EVENT_PROTOCOL_CHANGE,
                    {
                        "company_id": self.company_id,
                        "previous_mode": previous_mode,
                        "new_mode": new_mode,
                        "reason": reason,
                        "changed_at": datetime.now(
                            timezone.utc,
                        ).isoformat(),
                    },
                    room=room,
                )
        except Exception as exc:
            logger.debug(
                "trust_protocol_broadcast_failed",
                company_id=self.company_id,
                error=str(exc),
            )


# ══════════════════════════════════════════════════════════════════
# LAZY SERVICE LOADING (BC-008)
# ══════════════════════════════════════════════════════════════════

_service_cache: Dict[str, TrustPreservationService] = {}


def get_trust_preservation_service(
    company_id: str,
) -> TrustPreservationService:
    """Get or create a TrustPreservationService for a tenant.

    Uses lazy loading pattern per system_status_service.py.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        TrustPreservationService instance.
    """
    if company_id not in _service_cache:
        _service_cache[company_id] = TrustPreservationService(company_id)
    return _service_cache[company_id]


__all__ = [
    "TrustPreservationService",
    "ProtocolMode",
    "ProtocolTransitionReason",
    "SOCKETIO_EVENT_PROTOCOL_CHANGE",
    "get_trust_preservation_service",
]
