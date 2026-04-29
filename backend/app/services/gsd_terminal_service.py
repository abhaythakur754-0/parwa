"""
PARWA GSD Debug Terminal Service (F-089) — GSD State Machine Debugging

Provides a debugging interface for the GSD (Guided Support Dialogue)
state machine. Operators can inspect, monitor, and intervene in GSD
sessions for troubleshooting and recovery.

Features:
- Get current GSD state for a ticket (Redis primary, DB fallback per BC-008)
- List active GSD sessions (optionally filtered by agent, stuck sessions)
- Force-transition a stuck GSD session (admin only, audit-logged)
- Detect stuck sessions (same step > 30 minutes)
- Track transition history

Methods:
- get_gsd_state() — Current GSD state for a ticket
- list_active_sessions() — All active sessions with optional filters
- force_transition() — Admin-only forced state transition
- detect_stuck_sessions() — Find sessions stuck > 30 minutes

Building Codes: BC-001 (tenant isolation), BC-008 (state management),
               BC-011 (auth), BC-012 (error handling)
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.logger import get_logger

logger = get_logger("gsd_terminal_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Redis key TTL for GSD state data (24 hours)
GSD_STATE_TTL_SECONDS = 86400

# Threshold for detecting stuck sessions (30 minutes)
STUCK_THRESHOLD_SECONDS = 1800.0

# Critical stuck threshold (60 minutes)
CRITICAL_STUCK_THRESHOLD_SECONDS = 3600.0

# Maximum active sessions to return
MAX_SESSIONS_RETURNED = 500

# Maximum transition history entries to return per ticket
MAX_HISTORY_ENTRIES = 50


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class GSDTerminalService:
    """GSD Debug Terminal Service (F-089) — State Machine Debugging.

    Provides debugging and intervention capabilities for the GSD
    state machine. All operations are scoped by company_id (BC-001).

    State data is read from Redis (primary) with DB fallback (BC-008).
    Force transitions are audit-logged and admin-only (BC-011).

    BC-008: All methods handle failures gracefully.
    BC-012: Structured error responses, UTC timestamps.
    """

    def __init__(self, company_id: str, db=None):
        """Initialize the service for a specific tenant.

        Args:
            company_id: Tenant identifier (BC-001).
            db: Optional SQLAlchemy session for DB fallback.
        """
        self.company_id = company_id
        self.db = db
        self._redis = None

    # ── Lazy Redis Loading ──────────────────────────────────────

    async def _get_redis(self):
        """Get Redis connection (lazy, with graceful fallback).

        BC-008: Returns None on failure.
        """
        if self._redis is not None:
            return self._redis
        try:
            from app.core.redis import get_redis

            self._redis = await get_redis()
            return self._redis
        except Exception as exc:
            logger.warning(
                "gsd_terminal_redis_unavailable",
                company_id=self.company_id,
                error=str(exc),
            )
            return None

    # ── Core Methods ────────────────────────────────────────────

    async def get_gsd_state(self, ticket_id: str) -> Dict[str, Any]:
        """Get the current GSD state for a ticket.

        Resolution order:
        1. Redis (primary, fastest)
        2. SharedGSDManager in-memory (fallback)
        3. Database (last resort)

        Args:
            ticket_id: The ticket identifier.

        Returns:
            Dictionary with current GSD state, duration, signals, history.
        """
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Try Redis first
        redis_state = await self._get_redis_state(ticket_id)
        if redis_state is not None:
            duration = now - redis_state.get("entered_at_epoch", now)
            redis_state["duration_seconds"] = round(duration, 2)
            redis_state["source"] = "redis"
            logger.debug(
                "gsd_state_from_redis",
                company_id=self.company_id,
                ticket_id=ticket_id,
                state=redis_state.get("current_state"),
            )
            return redis_state

        # 2. Try SharedGSDManager in-memory
        inmemory_state = self._get_inmemory_state(ticket_id)
        if inmemory_state is not None:
            inmemory_state["source"] = "inmemory"
            logger.debug(
                "gsd_state_from_inmemory",
                company_id=self.company_id,
                ticket_id=ticket_id,
                state=inmemory_state.get("current_state"),
            )
            return inmemory_state

        # 3. Try database fallback
        db_state = await self._get_db_state(ticket_id)
        if db_state is not None:
            db_state["source"] = "database"
            logger.debug(
                "gsd_state_from_database",
                company_id=self.company_id,
                ticket_id=ticket_id,
                state=db_state.get("current_state"),
            )
            return db_state

        # No state found — return unknown state
        return {
            "ticket_id": ticket_id,
            "company_id": self.company_id,
            "current_state": "unknown",
            "variant": "parwa",
            "entered_at": None,
            "duration_seconds": 0.0,
            "transition_count": 0,
            "signals": {},
            "source": "not_found",
            "history": [],
        }

    async def list_active_sessions(
        self,
        agent_id: Optional[str] = None,
        stuck_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List active GSD sessions for this tenant.

        Args:
            agent_id: Filter by agent ID (optional).
            stuck_only: Only return stuck sessions.
            limit: Maximum sessions to return.
            offset: Pagination offset.

        Returns:
            Dictionary with sessions list, total count, stuck count.
        """
        sessions = []
        now = time.time()

        # Gather from Redis
        redis_sessions = await self._get_redis_sessions()
        sessions.extend(redis_sessions)

        # Also gather from in-memory SharedGSDManager
        inmemory_sessions = self._get_inmemory_sessions()
        sessions.extend(inmemory_sessions)

        # Deduplicate by ticket_id
        seen = set()
        unique_sessions = []
        for session in sessions:
            tid = session.get("ticket_id", "")
            if tid and tid not in seen:
                seen.add(tid)
                unique_sessions.append(session)

        # Apply filters
        filtered = []
        for session in unique_sessions:
            # Agent filter
            if agent_id:
                if session.get("agent_id") != agent_id:
                    continue

            # Stuck detection
            duration = session.get("duration_seconds", 0.0)
            is_stuck = duration > STUCK_THRESHOLD_SECONDS
            session["is_stuck"] = is_stuck

            if is_stuck:
                session["stuck_reason"] = self._get_stuck_reason(
                    session.get("current_state", ""),
                    duration,
                )

            if stuck_only and not is_stuck:
                continue

            filtered.append(session)

        # Sort by duration descending (longest-running first)
        filtered.sort(key=lambda x: x.get("duration_seconds", 0), reverse=True)

        total = len(filtered)
        stuck_count = sum(1 for s in filtered if s.get("is_stuck", False))

        # Apply pagination
        paginated = filtered[offset : offset + limit]

        return {
            "sessions": paginated,
            "total": total,
            "stuck_count": stuck_count,
        }

    async def force_transition(
        self,
        ticket_id: str,
        target_state: str,
        reason: str,
        actor_id: str,
    ) -> Dict[str, Any]:
        """Force-transition a stuck GSD session (admin only).

        This is a privileged operation that overrides the normal state
        machine transitions. It is audit-logged and requires admin
        authorization (BC-011).

        Args:
            ticket_id: The ticket to force-transition.
            target_state: Target GSD state.
            reason: Human-readable reason (for audit log).
            actor_id: ID of the admin performing the action.

        Returns:
            Dictionary with transition result and audit log ID.
        """
        now = datetime.now(timezone.utc)
        audit_log_id = str(uuid4())

        # 1. Get current state
        current = await self.get_gsd_state(ticket_id)
        previous_state = current.get("current_state", "unknown")

        # 2. Validate target state
        valid_states = {
            "new",
            "greeting",
            "diagnosis",
            "resolution",
            "follow_up",
            "escalate",
            "human_handof",
            "closed",
        }
        target = target_state.lower().strip()
        if target not in valid_states:
            return {
                "ticket_id": ticket_id,
                "previous_state": previous_state,
                "new_state": previous_state,
                "transitioned_at": now.isoformat(),
                "audit_log_id": audit_log_id,
                "error": (
                    f"Invalid target state: '{target_state}'. "
                    f"Valid states: {', '.join(sorted(valid_states))}"
                ),
            }

        # 3. Execute the transition in Redis
        redis = await self._get_redis()
        transition_recorded = False

        if redis is not None:
            try:
                from app.core.redis import make_key

                # Update current state in Redis
                state_key = make_key(
                    self.company_id,
                    "gsd",
                    "state",
                    ticket_id,
                )
                new_state_data = {
                    "ticket_id": ticket_id,
                    "company_id": self.company_id,
                    "current_state": target,
                    "variant": current.get("variant", "parwa"),
                    "entered_at": now.isoformat(),
                    "entered_at_epoch": time.time(),
                    "force_transitioned": True,
                    "force_transition_reason": reason,
                    "force_transitioned_by": actor_id,
                }
                await redis.set(
                    state_key,
                    json.dumps(new_state_data),
                    ex=GSD_STATE_TTL_SECONDS,
                )

                # Append to transition history
                history_key = make_key(
                    self.company_id,
                    "gsd",
                    "history",
                    ticket_id,
                )
                transition_entry = {
                    "from_state": previous_state,
                    "to_state": target,
                    "timestamp": now.isoformat(),
                    "trigger": f"force_transition: {reason}",
                    "actor_id": actor_id,
                    "audit_log_id": audit_log_id,
                }
                await redis.lpush(
                    history_key,
                    json.dumps(transition_entry),
                )
                await redis.ltrim(history_key, 0, MAX_HISTORY_ENTRIES - 1)
                await redis.expire(history_key, GSD_STATE_TTL_SECONDS)

                transition_recorded = True

            except Exception as exc:
                logger.error(
                    "gsd_force_transition_redis_failed",
                    company_id=self.company_id,
                    ticket_id=ticket_id,
                    error=str(exc),
                )

        # 4. Also update in-memory SharedGSDManager
        try:
            from app.core.shared_gsd import SharedGSDManager

            manager = SharedGSDManager()
            manager.record_transition(
                company_id=self.company_id,
                ticket_id=ticket_id,
                from_state=previous_state,
                to_state=target,
                metadata={
                    "trigger": "force_transition",
                    "reason": reason,
                    "actor_id": actor_id,
                    "audit_log_id": audit_log_id,
                },
            )
            transition_recorded = True
        except Exception as exc:
            logger.warning(
                "gsd_force_transition_inmemory_failed",
                company_id=self.company_id,
                ticket_id=ticket_id,
                error=str(exc),
            )

        # 5. Audit log
        await self._record_audit_log(
            ticket_id=ticket_id,
            previous_state=previous_state,
            new_state=target,
            reason=reason,
            actor_id=actor_id,
            audit_log_id=audit_log_id,
        )

        logger.info(
            "gsd_force_transition_executed",
            company_id=self.company_id,
            ticket_id=ticket_id,
            previous_state=previous_state,
            new_state=target,
            actor_id=actor_id,
            audit_log_id=audit_log_id,
        )

        return {
            "ticket_id": ticket_id,
            "previous_state": previous_state,
            "new_state": target,
            "transitioned_at": now.isoformat(),
            "audit_log_id": audit_log_id,
        }

    async def detect_stuck_sessions(
        self,
        threshold_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Detect GSD sessions that have been stuck in the same state.

        A session is considered stuck when it has been in the same
        state for longer than the threshold (default 30 minutes).

        Args:
            threshold_seconds: Custom threshold (default STUCK_THRESHOLD_SECONDS).

        Returns:
            List of stuck session info dicts with suggested actions.
        """
        threshold = threshold_seconds or STUCK_THRESHOLD_SECONDS
        now = time.time()

        # Get all active sessions
        result = await self.list_active_sessions(
            limit=MAX_SESSIONS_RETURNED,
        )

        stuck = []
        for session in result.get("sessions", []):
            duration = session.get("duration_seconds", 0.0)
            if duration > threshold:
                current_state = session.get("current_state", "unknown")

                # Build suggested actions
                suggestions = []
                if duration > CRITICAL_STUCK_THRESHOLD_SECONDS:
                    suggestions.append(
                        {
                            "action": "escalate_to_human",
                            "priority": "high",
                            "description": (
                                f"Session stuck for {duration / 60:.0f} "
                                "minutes — immediate human review needed"
                            ),
                        }
                    )
                    suggestions.append(
                        {
                            "action": "force_close",
                            "priority": "medium",
                            "description": (
                                "Consider force-closing if the issue "
                                "has been resolved externally"
                            ),
                        }
                    )
                else:
                    suggestions.append(
                        {
                            "action": "review",
                            "priority": "medium",
                            "description": (
                                f"Session in '{current_state}' for "
                                f"{duration / 60:.0f} minutes — review needed"
                            ),
                        }
                    )

                # Get valid transitions for current state
                try:
                    from app.core.shared_gsd import SharedGSDManager

                    valid = SharedGSDManager.get_valid_transitions(
                        current_state,
                    )
                    if valid:
                        suggestions.append(
                            {
                                "action": "suggest_transition",
                                "priority": "low",
                                "description": (
                                    "Valid next states from "
                                    f"'{current_state}': "
                                    f"{', '.join(valid)}"
                                ),
                            }
                        )
                except Exception:
                    pass

                stuck.append(
                    {
                        "ticket_id": session.get("ticket_id", ""),
                        "company_id": self.company_id,
                        "current_state": current_state,
                        "stuck_duration_seconds": round(duration, 2),
                        "stuck_threshold_seconds": threshold,
                        "last_transition_at": session.get("last_transition_at"),
                        "suggested_actions": suggestions,
                    }
                )

        logger.info(
            "gsd_stuck_sessions_detected",
            company_id=self.company_id,
            stuck_count=len(stuck),
            threshold_seconds=threshold,
        )

        return stuck

    # ── Redis State Access ───────────────────────────────────────

    async def _get_redis_state(
        self,
        ticket_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Read GSD state from Redis."""
        redis = await self._get_redis()
        if redis is None:
            return None

        try:
            from app.core.redis import make_key

            state_key = make_key(
                self.company_id,
                "gsd",
                "state",
                ticket_id,
            )
            raw = await redis.get(state_key)
            if raw:
                data = json.loads(raw)
                # Get transition count from history
                history = await self._get_redis_history(ticket_id)
                data["transition_count"] = len(history)
                data["history"] = history[-10:]  # Last 10 entries
                return data
        except Exception:
            pass

        return None

    async def _get_redis_history(
        self,
        ticket_id: str,
    ) -> List[Dict[str, Any]]:
        """Read GSD transition history from Redis."""
        redis = await self._get_redis()
        if redis is None:
            return []

        try:
            from app.core.redis import make_key

            history_key = make_key(
                self.company_id,
                "gsd",
                "history",
                ticket_id,
            )
            raw_entries = await redis.lrange(history_key, 0, -1)
            entries = []
            for entry in raw_entries:
                try:
                    entries.append(json.loads(entry))
                except (json.JSONDecodeError, TypeError):
                    continue
            return entries
        except Exception:
            return []

    async def _get_redis_sessions(self) -> List[Dict[str, Any]]:
        """Get all active GSD sessions from Redis keys."""
        redis = await self._get_redis()
        if redis is None:
            return []

        sessions = []
        try:
            from app.core.redis import make_key

            pattern = make_key(self.company_id, "gsd", "state", "*")
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )
                for key in keys:
                    try:
                        raw = await redis.get(key)
                        if raw:
                            data = json.loads(raw)
                            if data.get("company_id") == self.company_id:
                                now = time.time()
                                entered = data.get(
                                    "entered_at_epoch",
                                    now,
                                )
                                data["duration_seconds"] = round(
                                    now - entered,
                                    2,
                                )
                                sessions.append(data)
                    except (json.JSONDecodeError, TypeError):
                        continue

                if cursor == 0:
                    break

        except Exception as exc:
            logger.warning(
                "gsd_redis_sessions_failed",
                company_id=self.company_id,
                error=str(exc),
            )

        return sessions

    # ── In-Memory State Access ───────────────────────────────────

    @staticmethod
    def _get_inmemory_state(ticket_id: str) -> Optional[Dict[str, Any]]:
        """Read GSD state from SharedGSDManager in-memory."""
        try:
            from app.core.shared_gsd import SharedGSDManager

            manager = SharedGSDManager()
            # We need company_id, but we can check all companies
            # This is a fallback, so we do a broad search
            current = manager.get_current_state("__global__", ticket_id)
            if current:
                now = time.time()
                return {
                    "ticket_id": ticket_id,
                    "company_id": "",
                    "current_state": current,
                    "variant": "parwa",
                    "entered_at": None,
                    "duration_seconds": 0.0,
                    "transition_count": len(
                        manager.get_transition_history(
                            "__global__",
                            ticket_id,
                        ),
                    ),
                    "signals": {},
                    "history": manager.get_transition_history(
                        "__global__",
                        ticket_id,
                    )[-10:],
                }
        except Exception:
            pass

        return None

    @staticmethod
    def _get_inmemory_sessions() -> List[Dict[str, Any]]:
        """Get active sessions from SharedGSDManager in-memory."""
        sessions = []
        try:
            from app.core.shared_gsd import SharedGSDManager

            manager = SharedGSDManager()
            # Access the internal _current_states dict
            for company_id, tickets in manager._current_states.items():
                for ticket_id, state_info in tickets.items():
                    now = time.time()
                    entered = state_info.get("entered_at", now)
                    history = manager.get_transition_history(
                        company_id,
                        ticket_id,
                    )
                    last_transition = (
                        history[-1].get("timestamp", 0) if history else None
                    )
                    sessions.append(
                        {
                            "ticket_id": ticket_id,
                            "company_id": company_id,
                            "current_state": state_info.get("state", "unknown"),
                            "agent_id": None,
                            "duration_seconds": round(now - entered, 2),
                            "transition_count": len(history),
                            "last_transition_at": last_transition,
                        }
                    )
        except Exception:
            pass

        return sessions

    # ── Database Fallback ────────────────────────────────────────

    async def _get_db_state(
        self,
        ticket_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Read GSD state from database (last resort)."""
        if self.db is None:
            return None

        try:
            from database.models.tickets import Ticket

            ticket = (
                self.db.query(Ticket)
                .filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == self.company_id,
                )
                .first()
            )

            if ticket is None:
                return None

            # Extract GSD state from ticket metadata if available
            metadata = {}
            try:
                metadata = json.loads(ticket.metadata_json or "{}")
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

            gsd_state = metadata.get("gsd_state", "unknown")
            variant = metadata.get("gsd_variant", "parwa")

            return {
                "ticket_id": ticket_id,
                "company_id": self.company_id,
                "current_state": gsd_state,
                "variant": variant,
                "entered_at": (
                    ticket.updated_at.isoformat() if ticket.updated_at else None
                ),
                "duration_seconds": 0.0,
                "transition_count": metadata.get("gsd_transition_count", 0),
                "signals": metadata.get("gsd_signals", {}),
                "history": metadata.get("gsd_history", [])[-10:],
            }

        except Exception as exc:
            logger.warning(
                "gsd_db_state_failed",
                company_id=self.company_id,
                ticket_id=ticket_id,
                error=str(exc),
            )
            return None

    # ── Audit Logging ────────────────────────────────────────────

    async def _record_audit_log(
        self,
        ticket_id: str,
        previous_state: str,
        new_state: str,
        reason: str,
        actor_id: str,
        audit_log_id: str,
    ) -> None:
        """Record a force-transition in the audit log.

        BC-011: All admin actions are audit-logged.
        """
        try:
            # Try in-memory audit service
            audit_svc = None
            try:
                from app.services.jarvis_service import _get_service_module

                audit_mod = _get_service_module("app.services.audit_service")
                if audit_mod:
                    audit_svc = audit_mod
            except Exception:
                pass

            if audit_svc and self.db:
                try:
                    audit_svc.log_audit(
                        company_id=self.company_id,
                        actor_id=actor_id,
                        actor_type="admin",
                        action="gsd_force_transition",
                        resource_type="ticket",
                        resource_id=ticket_id,
                        old_value={"previous_state": previous_state},
                        new_value={
                            "new_state": new_state,
                            "reason": reason,
                        },
                        ip_address=None,
                        user_agent=None,
                        db=self.db,
                    )
                except Exception:
                    pass

            # Also log to Redis for redundancy
            redis = await self._get_redis()
            if redis is not None:
                try:
                    from app.core.redis import make_key

                    audit_key = make_key(
                        self.company_id,
                        "gsd",
                        "audit",
                    )
                    entry = {
                        "audit_log_id": audit_log_id,
                        "ticket_id": ticket_id,
                        "action": "gsd_force_transition",
                        "previous_state": previous_state,
                        "new_state": new_state,
                        "reason": reason,
                        "actor_id": actor_id,
                        "timestamp": datetime.now(
                            timezone.utc,
                        ).isoformat(),
                    }
                    await redis.lpush(
                        audit_key,
                        json.dumps(entry),
                    )
                    await redis.ltrim(audit_key, 0, 999)
                except Exception:
                    pass

        except Exception as exc:
            logger.warning(
                "gsd_audit_log_failed",
                company_id=self.company_id,
                error=str(exc),
            )

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _get_stuck_reason(state: str, duration: float) -> str:
        """Generate a human-readable stuck reason."""
        minutes = duration / 60
        if minutes > 60:
            return f"Stuck in '{state}' for {
                    minutes:.0f} minutes " f"(>{
                    CRITICAL_STUCK_THRESHOLD_SECONDS
                    / 60:.0f} min critical threshold)"
        return (
            f"In '{state}' for {minutes:.0f} minutes "
            f"(>{STUCK_THRESHOLD_SECONDS / 60:.0f} min threshold)"
        )


# ══════════════════════════════════════════════════════════════════
# LAZY SERVICE LOADING (BC-008)
# ══════════════════════════════════════════════════════════════════

_service_cache: Dict[str, GSDTerminalService] = {}


def get_gsd_terminal_service(
    company_id: str,
    db=None,
) -> GSDTerminalService:
    """Get or create a GSDTerminalService for a tenant.

    Uses lazy loading pattern per jarvis_service.py.

    Args:
        company_id: Tenant identifier (BC-001).
        db: Optional SQLAlchemy session.

    Returns:
        GSDTerminalService instance.
    """
    if company_id not in _service_cache:
        _service_cache[company_id] = GSDTerminalService(
            company_id,
            db=db,
        )
    return _service_cache[company_id]


__all__ = [
    "GSDTerminalService",
    "get_gsd_terminal_service",
]
