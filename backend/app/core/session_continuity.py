"""
Session Continuity & Multi-Agent Collision Detection (SG-10).

Ensures exactly-one processing semantics across distributed agents via
ticket locking, collision detection, heartbeat monitoring, and handoff.

BC-001: All operations scoped by company_id.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC (ISO-8601).
"""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("session_continuity")


def _utcnow() -> str:
    """Return current UTC time as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(iso_str: str) -> datetime:
    """Parse an ISO-8601 UTC string into a datetime."""
    return datetime.fromisoformat(iso_str)


def _seconds_from_now(seconds: float) -> str:
    """Return an ISO-8601 UTC string for *now + seconds*."""
    return datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + seconds, tz=timezone.utc
    ).isoformat()


class SessionStatus(str, Enum):
    """Status of a processing session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    HANDOFF = "handoff"
    PREEMPTED = "preempted"
    EXPIRED = "expired"


class CollisionAction(str, Enum):
    """Action taken when collision is detected."""
    WAIT = "wait"
    PREEMPT = "preempt"
    MERGE = "merge"
    REJECT = "reject"
    QUEUE = "queue"


class LockStatus(str, Enum):
    """Status of a distributed lock."""
    ACQUIRED = "acquired"
    CONTESTED = "contested"
    RELEASED = "released"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"


@dataclass
class SessionLock:
    """Distributed lock on a ticket/session."""
    ticket_id: str
    company_id: str
    owner_id: str
    acquired_at: str
    expires_at: str
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollisionEvent:
    """Record of a collision detection event."""
    ticket_id: str
    company_id: str
    existing_owner: str
    contender_id: str
    detected_at: str
    action_taken: str
    resolution: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionRecord:
    """Record of an agent processing session."""
    session_id: str
    ticket_id: str
    company_id: str
    agent_id: str
    variant: str
    status: str
    started_at: str
    last_heartbeat_at: str
    completed_at: Optional[str] = None
    stage_reached: str = ""
    processing_steps: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HandoffRecord:
    """Record of a session handoff between agents."""
    ticket_id: str
    company_id: str
    from_agent: str
    to_agent: str
    handoff_at: str
    reason: str
    context_transferred: Dict[str, Any] = field(default_factory=dict)
    success: bool = True


@dataclass
class ContinuityConfig:
    """Per-company session continuity configuration."""
    company_id: str = ""
    lock_timeout_seconds: float = 300.0
    heartbeat_interval_seconds: float = 30.0
    max_heartbeat_misses: int = 3
    collision_strategy: str = "wait"
    session_ttl_seconds: float = 3600.0
    enable_heartbeat_monitoring: bool = True
    max_concurrent_sessions_per_agent: int = 10
    handoff_timeout_seconds: float = 60.0


class SessionContinuityManager:
    """Session Continuity & Multi-Agent Collision Detection (SG-10).

    Ensures only one agent processes a ticket at a time across
    a distributed deployment.  Provides ticket locking, collision
    detection, heartbeat monitoring, and graceful handoff.

    BC-001: company_id first parameter on all public methods.
    BC-008: Every public method wrapped in try/except — never crash.
    BC-012: All timestamps UTC.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._locks: Dict[Tuple[str, str], SessionLock] = {}
        self._sessions: Dict[str, SessionRecord] = {}
        self._ticket_sessions: Dict[Tuple[str, str],
                                    List[str]] = defaultdict(list)
        self._collision_events: Dict[str,
                                     List[CollisionEvent]] = defaultdict(list)
        self._handoff_records: Dict[str,
                                    List[HandoffRecord]] = defaultdict(list)
        self._configs: Dict[str, ContinuityConfig] = {}
        self._agent_session_counts: Dict[str, int] = defaultdict(int)
        self._listeners: List[Callable] = []
        self._max_collision_events = 200
        self._max_handoff_records = 200
        self._total_locks_acquired: int = 0
        self._total_locks_released: int = 0
        self._total_acquire_attempts: int = 0
        self._total_collisions: int = 0
        self._stale_sessions_recovered: int = 0

    # ── Configuration ─────────────────────────────────────────────

    def configure(self, company_id: str,
                  config: ContinuityConfig) -> Dict[str, Any]:
        """Set per-company continuity configuration (BC-001). Returns success dict."""
        try:
            if not company_id:
                return {"success": False, "error": "company_id is required"}
            config.company_id = company_id
            self._configs[company_id] = config
            logger.info("session_continuity_configured", company_id=company_id,
                        strategy=config.collision_strategy)
            return {"success": True}
        except Exception as exc:
            logger.error(
                "configure_failed",
                company_id=company_id,
                error=str(exc))
            return {"success": False, "error": str(exc)}

    def get_config(self, company_id: str) -> ContinuityConfig:
        """Get continuity config for a company, returning defaults if unset (BC-001)."""
        try:
            return self._configs.get(
                company_id, ContinuityConfig(
                    company_id=company_id))
        except Exception as exc:
            logger.error(
                "get_config_failed",
                company_id=company_id,
                error=str(exc))
            return ContinuityConfig(company_id=company_id)

    # ── Lock Operations ───────────────────────────────────────────

    def acquire_lock(self,
                     company_id: str,
                     ticket_id: str,
                     agent_id: str,
                     metadata: Optional[Dict[str,
                                             Any]] = None) -> Dict[str,
                                                                   Any]:
        """Acquire a processing lock on a ticket (BC-001).

        If locked by another agent, runs collision detection with the
        configured strategy.  Returns ``{success, lock_status, action}``.
        """
        try:
            if not company_id or not ticket_id or not agent_id:
                return {
                    "success": False,
                    "lock_status": LockStatus.NOT_FOUND.value,
                    "action": "invalid_input",
                    "error": "company_id, ticket_id, and agent_id are required"}
            config = self.get_config(company_id)
            key = (company_id, ticket_id)
            now = _utcnow()
            with self._lock:
                self._total_acquire_attempts += 1
                existing = self._locks.get(key)
                if existing is None:
                    return self._do_acquire(
                        key, company_id, ticket_id, agent_id, config, now, metadata or {})
                # Check expiry — release stale lock
                if _parse_utc(
                        existing.expires_at) < datetime.now(
                        timezone.utc):
                    logger.info(
                        "lock_expired_auto_release",
                        company_id=company_id,
                        ticket_id=ticket_id,
                        expired_owner=existing.owner_id)
                    self._remove_lock(key)
                    self._emit_event(
                        "lock_expired", {
                            "company_id": company_id, "ticket_id": ticket_id, "new_owner": agent_id})
                    return self._do_acquire(
                        key, company_id, ticket_id, agent_id, config, now, metadata or {})
                # Same owner — idempotent re-acquire
                if existing.owner_id == agent_id:
                    self._locks[key] = SessionLock(
                        ticket_id=ticket_id,
                        company_id=company_id,
                        owner_id=agent_id,
                        acquired_at=existing.acquired_at,
                        expires_at=_seconds_from_now(
                            config.lock_timeout_seconds),
                        status=LockStatus.ACQUIRED.value,
                        metadata=metadata or existing.metadata)
                    return {
                        "success": True,
                        "lock_status": LockStatus.ACQUIRED.value,
                        "action": "renewed"}
                # Contended — run collision resolution
                return self._resolve_collision(existing, agent_id, company_id,
                                               ticket_id, config, key, now,
                                               metadata or {})
        except Exception as exc:
            logger.error("acquire_lock_failed", company_id=company_id,
                         ticket_id=ticket_id, error=str(exc))
            return {
                "success": False,
                "lock_status": "error",
                "action": "error",
                "error": str(exc)}

    def release_lock(self, company_id: str, ticket_id: str,
                     agent_id: str) -> Dict[str, Any]:
        """Release a ticket lock. Only the lock owner may release (BC-001)."""
        try:
            key = (company_id, ticket_id)
            with self._lock:
                existing = self._locks.get(key)
                if existing is None:
                    return {"success": False,
                            "lock_status": LockStatus.NOT_FOUND.value}
                if existing.owner_id != agent_id:
                    return {"success": False, "lock_status": existing.status,
                            "error": "only the lock owner may release"}
                self._remove_lock(key)
                self._total_locks_released += 1
                logger.info("lock_released", company_id=company_id,
                            ticket_id=ticket_id, agent_id=agent_id)
                self._emit_event(
                    "lock_released", {
                        "company_id": company_id, "ticket_id": ticket_id, "agent_id": agent_id})
                return {
                    "success": True,
                    "lock_status": LockStatus.RELEASED.value}
        except Exception as exc:
            logger.error(
                "release_lock_failed",
                company_id=company_id,
                error=str(exc))
            return {
                "success": False,
                "lock_status": "error",
                "error": str(exc)}

    def renew_lock(self, company_id: str, ticket_id: str,
                   agent_id: str) -> Dict[str, Any]:
        """Extend the TTL of an existing lock. Owner-only operation (BC-001)."""
        try:
            key = (company_id, ticket_id)
            config = self.get_config(company_id)
            with self._lock:
                existing = self._locks.get(key)
                if existing is None:
                    return {"success": False,
                            "lock_status": LockStatus.NOT_FOUND.value}
                if existing.owner_id != agent_id:
                    return {"success": False, "lock_status": existing.status,
                            "error": "only the lock owner may renew"}
                renewed = SessionLock(
                    ticket_id=ticket_id,
                    company_id=company_id,
                    owner_id=agent_id,
                    acquired_at=existing.acquired_at,
                    expires_at=_seconds_from_now(
                        config.lock_timeout_seconds),
                    status=LockStatus.ACQUIRED.value,
                    metadata=existing.metadata)
                self._locks[key] = renewed
                return {
                    "success": True,
                    "lock_status": LockStatus.ACQUIRED.value,
                    "new_expires_at": renewed.expires_at}
        except Exception as exc:
            logger.error(
                "renew_lock_failed",
                company_id=company_id,
                error=str(exc))
            return {
                "success": False,
                "lock_status": "error",
                "error": str(exc)}

    def check_lock(self, company_id: str, ticket_id: str) -> Dict[str, Any]:
        """Get lock status without acquiring (BC-001). Returns ``{locked, owner_id, status}``."""
        try:
            key = (company_id, ticket_id)
            with self._lock:
                existing = self._locks.get(key)
                if existing is None:
                    return {"locked": False, "owner_id": None,
                            "status": LockStatus.NOT_FOUND.value}
                if _parse_utc(
                        existing.expires_at) < datetime.now(
                        timezone.utc):
                    return {"locked": False, "owner_id": None,
                            "status": LockStatus.EXPIRED.value}
                return {"locked": True, "owner_id": existing.owner_id,
                        "status": existing.status}
        except Exception as exc:
            logger.error(
                "check_lock_failed",
                company_id=company_id,
                error=str(exc))
            return {
                "locked": False,
                "owner_id": None,
                "status": "error",
                "error": str(exc)}

    def get_lock_info(self, company_id: str,
                      ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get full lock details for a ticket, or None (BC-001)."""
        try:
            key = (company_id, ticket_id)
            with self._lock:
                existing = self._locks.get(key)
                if existing is None:
                    return None
                return {
                    "ticket_id": existing.ticket_id,
                    "company_id": existing.company_id,
                    "owner_id": existing.owner_id,
                    "acquired_at": existing.acquired_at,
                    "expires_at": existing.expires_at,
                    "status": existing.status,
                    "metadata": existing.metadata}
        except Exception as exc:
            logger.error(
                "get_lock_info_failed",
                company_id=company_id,
                error=str(exc))
            return None

    def is_ticket_locked(self, company_id: str, ticket_id: str) -> bool:
        """Check whether a ticket is currently locked and not expired (BC-001)."""
        try:
            return self.check_lock(company_id, ticket_id).get("locked", False)
        except Exception as exc:
            logger.error(
                "is_ticket_locked_failed",
                company_id=company_id,
                error=str(exc))
            return False

    def get_ticket_owner(self, company_id: str,
                         ticket_id: str) -> Optional[str]:
        """Get the agent currently owning the ticket lock, or None (BC-001)."""
        try:
            return self.check_lock(company_id, ticket_id).get("owner_id")
        except Exception as exc:
            logger.error(
                "get_ticket_owner_failed",
                company_id=company_id,
                error=str(exc))
            return None

    # ── Session Operations ────────────────────────────────────────

    def register_session(self,
                         company_id: str,
                         ticket_id: str,
                         agent_id: str,
                         variant: str,
                         metadata: Optional[Dict[str,
                                                 Any]] = None) -> Dict[str,
                                                                       Any]:
        """Register a new processing session. Ticket must be locked by agent (BC-001).

        Returns ``{success: True, session_id: ...}`` or error dict.
        """
        try:
            config = self.get_config(company_id)
            with self._lock:
                key = (company_id, ticket_id)
                lock = self._locks.get(key)
                if lock is None or lock.owner_id != agent_id:
                    return {"success": False,
                            "error": "ticket not locked by this agent"}
                if self._agent_session_counts.get(
                        agent_id, 0) >= config.max_concurrent_sessions_per_agent:
                    return {"success": False,
                            "error": f"agent {agent_id} at concurrency limit "
                            f"({config.max_concurrent_sessions_per_agent})"}
                session_id = str(uuid.uuid4())
                now = _utcnow()
                self._sessions[session_id] = SessionRecord(
                    session_id=session_id, ticket_id=ticket_id, company_id=company_id,
                    agent_id=agent_id, variant=variant, status=SessionStatus.ACTIVE.value,
                    started_at=now, last_heartbeat_at=now, metadata=metadata or {})
                self._ticket_sessions[key].append(session_id)
                self._agent_session_counts[agent_id] += 1
                logger.info("session_registered", session_id=session_id,
                            company_id=company_id, agent_id=agent_id)
                self._emit_event(
                    "session_registered", {
                        "session_id": session_id, "company_id": company_id, "agent_id": agent_id})
                return {"success": True, "session_id": session_id}
        except Exception as exc:
            logger.error(
                "register_session_failed",
                company_id=company_id,
                error=str(exc))
            return {"success": False, "error": str(exc)}

    def update_session(self, company_id: str, session_id: str,
                       updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update fields on an active session (stage_reached, processing_steps, etc.).

        Only active sessions owned by this company may be updated (BC-001).
        """
        try:
            allowed = {
                "stage_reached",
                "processing_steps",
                "metadata",
                "variant"}
            with self._lock:
                session = self._sessions.get(session_id)
                if session is None:
                    return {"success": False, "error": "session not found"}
                if session.company_id != company_id:
                    return {"success": False, "error": "company_id mismatch"}
                if session.status != SessionStatus.ACTIVE.value:
                    return {"success": False, "error": "session is not active"}
                for k, v in updates.items():
                    if k in allowed and hasattr(session, k):
                        setattr(session, k, v)
                return {"success": True}
        except Exception as exc:
            logger.error(
                "update_session_failed",
                company_id=company_id,
                error=str(exc))
            return {"success": False, "error": str(exc)}

    def heartbeat(self, company_id: str, session_id: str) -> Dict[str, Any]:
        """Update the heartbeat timestamp for an active session (BC-001)."""
        try:
            with self._lock:
                session = self._sessions.get(session_id)
                if session is None:
                    return {"success": False, "error": "session not found"}
                if session.company_id != company_id:
                    return {"success": False, "error": "company_id mismatch"}
                if session.status != SessionStatus.ACTIVE.value:
                    return {"success": False, "error": "session is not active"}
                session.last_heartbeat_at = _utcnow()
                return {"success": True}
        except Exception as exc:
            logger.error(
                "heartbeat_failed",
                company_id=company_id,
                error=str(exc))
            return {"success": False, "error": str(exc)}

    def complete_session(self, company_id: str,
                         session_id: str) -> Dict[str, Any]:
        """Mark session completed and release its ticket lock (BC-001)."""
        try:
            with self._lock:
                session = self._sessions.get(session_id)
                if session is None:
                    return {"success": False, "error": "session not found"}
                if session.company_id != company_id:
                    return {"success": False, "error": "company_id mismatch"}
                session.status = SessionStatus.COMPLETED.value
                session.completed_at = _utcnow()
                self._agent_session_counts[session.agent_id] = max(
                    0, self._agent_session_counts.get(session.agent_id, 0) - 1)
                self.release_lock(
                    session.company_id,
                    session.ticket_id,
                    session.agent_id)
                logger.info("session_completed", session_id=session_id,
                            company_id=company_id)
                self._emit_event("session_completed",
                                 {"session_id": session_id,
                                  "company_id": company_id,
                                  "agent_id": session.agent_id})
                return {"success": True}
        except Exception as exc:
            logger.error(
                "complete_session_failed",
                company_id=company_id,
                error=str(exc))
            return {"success": False, "error": str(exc)}

    def fail_session(self, company_id: str, session_id: str,
                     error: str = "") -> Dict[str, Any]:
        """Mark session as failed and release its ticket lock (BC-001)."""
        try:
            with self._lock:
                session = self._sessions.get(session_id)
                if session is None:
                    return {"success": False, "error": "session not found"}
                if session.company_id != company_id:
                    return {"success": False, "error": "company_id mismatch"}
                session.status = SessionStatus.FAILED.value
                session.completed_at = _utcnow()
                if error:
                    session.metadata["error"] = error
                self._agent_session_counts[session.agent_id] = max(
                    0, self._agent_session_counts.get(session.agent_id, 0) - 1)
                self.release_lock(
                    session.company_id,
                    session.ticket_id,
                    session.agent_id)
                logger.error("session_failed", session_id=session_id,
                             company_id=company_id, error=error)
                self._emit_event(
                    "session_failed", {
                        "session_id": session_id, "company_id": company_id, "error": error})
                return {"success": True}
        except Exception as exc:
            logger.error(
                "fail_session_failed",
                company_id=company_id,
                error=str(exc))
            return {"success": False, "error": str(exc)}

    # ── Stale Session Detection ───────────────────────────────────

    def detect_stale_sessions(self, company_id: str) -> Dict[str, Any]:
        """Find active sessions with missed heartbeats (BC-001).

        Stale when ``now - last_heartbeat > interval * max_misses``.
        Returns ``{stale_sessions: [...], monitoring_enabled: bool}``.
        """
        try:
            config = self.get_config(company_id)
            if not config.enable_heartbeat_monitoring:
                return {"stale_sessions": [], "monitoring_enabled": False}
            threshold = config.heartbeat_interval_seconds * config.max_heartbeat_misses
            now = datetime.now(timezone.utc)
            stale: List[Dict[str, Any]] = []
            with self._lock:
                for s in list(self._sessions.values()):
                    if (s.company_id == company_id
                            and s.status == SessionStatus.ACTIVE.value):
                        elapsed = (
                            now -
                            _parse_utc(
                                s.last_heartbeat_at)).total_seconds()
                        if elapsed > threshold:
                            stale.append({"session_id": s.session_id,
                                          "ticket_id": s.ticket_id,
                                          "agent_id": s.agent_id,
                                          "last_heartbeat_at": s.last_heartbeat_at,
                                          "elapsed_seconds": round(elapsed, 2),
                                          "threshold_seconds": threshold})
            logger.info("stale_sessions_detected", company_id=company_id,
                        count=len(stale))
            return {"stale_sessions": stale, "monitoring_enabled": True}
        except Exception as exc:
            logger.error(
                "detect_stale_failed",
                company_id=company_id,
                error=str(exc))
            return {"stale_sessions": [], "error": str(exc)}

    def force_release_stale(self, company_id: str,
                            ticket_id: str) -> Dict[str, Any]:
        """Release a stale lock and expire its sessions (BC-001).

        Returns ``{success: True, sessions_expired: int}``.
        """
        try:
            key = (company_id, ticket_id)
            expired = 0
            with self._lock:
                if self._locks.get(key) is None:
                    return {"success": False, "error": "no lock found",
                            "sessions_expired": 0}
                for sid in self._ticket_sessions.get(key, []):
                    s = self._sessions.get(sid)
                    if s and s.status == SessionStatus.ACTIVE.value:
                        s.status = SessionStatus.EXPIRED.value
                        s.completed_at = _utcnow()
                        self._agent_session_counts[s.agent_id] = max(
                            0, self._agent_session_counts.get(s.agent_id, 0) - 1)
                        expired += 1
                self._remove_lock(key)
                self._stale_sessions_recovered += expired
                logger.info("stale_lock_released", company_id=company_id,
                            ticket_id=ticket_id, sessions_expired=expired)
                self._emit_event(
                    "stale_lock_released", {
                        "company_id": company_id, "ticket_id": ticket_id, "sessions_expired": expired})
                return {"success": True, "sessions_expired": expired}
        except Exception as exc:
            logger.error("force_release_stale_failed", company_id=company_id,
                         error=str(exc))
            return {"success": False, "error": str(exc), "sessions_expired": 0}

    # ── Handoff ───────────────────────────────────────────────────

    def initiate_handoff(self,
                         company_id: str,
                         ticket_id: str,
                         from_agent: str,
                         to_agent: str,
                         reason: str,
                         context: Optional[Dict[str,
                                                Any]] = None) -> Dict[str,
                                                                      Any]:
        """Transfer session ownership between agents (BC-001).

        ``from_agent`` must hold the lock.  Returns ``{handoff_id, sessions_handled}``.
        """
        try:
            key = (company_id, ticket_id)
            config = self.get_config(company_id)
            now = _utcnow()
            with self._lock:
                lock = self._locks.get(key)
                if lock is None:
                    return {
                        "success": False,
                        "error": "no lock found for ticket"}
                if lock.owner_id != from_agent:
                    return {
                        "success": False,
                        "error": f"lock owned by {
                            lock.owner_id}, not {from_agent}"}
                handled = 0
                for sid in self._ticket_sessions.get(key, []):
                    s = self._sessions.get(sid)
                    if s and s.status == SessionStatus.ACTIVE.value:
                        s.status = SessionStatus.HANDOFF.value
                        s.completed_at = now
                        self._agent_session_counts[from_agent] = max(
                            0, self._agent_session_counts.get(from_agent, 0) - 1)
                        handled += 1
                self._locks[key] = SessionLock(
                    ticket_id=ticket_id,
                    company_id=company_id,
                    owner_id=to_agent,
                    acquired_at=now,
                    expires_at=_seconds_from_now(
                        config.lock_timeout_seconds),
                    status=LockStatus.ACQUIRED.value,
                    metadata={
                        "handed_off_from": from_agent})
                self._handoff_records[company_id].append(
                    HandoffRecord(
                        ticket_id=ticket_id,
                        company_id=company_id,
                        from_agent=from_agent,
                        to_agent=to_agent,
                        handoff_at=now,
                        reason=reason,
                        context_transferred=context or {}))
                if len(
                        self._handoff_records[company_id]) > self._max_handoff_records:
                    self._handoff_records[company_id] = (
                        self._handoff_records[company_id][-self._max_handoff_records:])
                logger.info("handoff_completed", company_id=company_id,
                            from_agent=from_agent, to_agent=to_agent)
                self._emit_event("session_handoff",
                                 {"company_id": company_id,
                                  "ticket_id": ticket_id,
                                  "from_agent": from_agent,
                                  "to_agent": to_agent})
                return {"success": True, "handoff_id": str(uuid.uuid4()),
                        "sessions_handled": handled}
        except Exception as exc:
            logger.error("initiate_handoff_failed", company_id=company_id,
                         error=str(exc))
            return {"success": False, "error": str(exc)}

    # ── Query Operations ──────────────────────────────────────────

    def get_collision_events(self, company_id: str,
                             ticket_id: Optional[str] = None,
                             limit: int = 50) -> List[Dict[str, Any]]:
        """Get collision event history, newest first (BC-001)."""
        try:
            events = self._collision_events.get(company_id, [])
            if ticket_id:
                events = [e for e in events if e.ticket_id == ticket_id]
            return [{"ticket_id": e.ticket_id, "company_id": e.company_id,
                     "existing_owner": e.existing_owner, "contender_id": e.contender_id,
                     "detected_at": e.detected_at, "action_taken": e.action_taken,
                     "resolution": e.resolution, "metadata": e.metadata}
                    for e in reversed(events[-limit:])]
        except Exception as exc:
            logger.error("get_collision_events_failed", company_id=company_id,
                         error=str(exc))
            return []

    def get_session(self, company_id: str,
                    session_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a single session, or None (BC-001)."""
        try:
            s = self._sessions.get(session_id)
            if s is None or s.company_id != company_id:
                return None
            return {
                "session_id": s.session_id,
                "ticket_id": s.ticket_id,
                "company_id": s.company_id,
                "agent_id": s.agent_id,
                "variant": s.variant,
                "status": s.status,
                "started_at": s.started_at,
                "last_heartbeat_at": s.last_heartbeat_at,
                "completed_at": s.completed_at,
                "stage_reached": s.stage_reached,
                "processing_steps": s.processing_steps,
                "metadata": s.metadata}
        except Exception as exc:
            logger.error(
                "get_session_failed",
                company_id=company_id,
                error=str(exc))
            return None

    def get_active_sessions(self, company_id: str) -> List[Dict[str, Any]]:
        """List all active sessions for a company (BC-001)."""
        try:
            result: List[Dict[str, Any]] = []
            with self._lock:
                for s in self._sessions.values():
                    if (s.company_id == company_id
                            and s.status == SessionStatus.ACTIVE.value):
                        result.append({"session_id": s.session_id,
                                       "ticket_id": s.ticket_id,
                                       "agent_id": s.agent_id,
                                       "variant": s.variant,
                                       "started_at": s.started_at,
                                       "last_heartbeat_at": s.last_heartbeat_at,
                                       "stage_reached": s.stage_reached,
                                       "processing_steps": s.processing_steps})
            return result
        except Exception as exc:
            logger.error("get_active_sessions_failed", company_id=company_id,
                         error=str(exc))
            return []

    def get_agent_sessions(self, company_id: str,
                           agent_id: str) -> List[Dict[str, Any]]:
        """List all sessions (any status) for a specific agent (BC-001)."""
        try:
            result: List[Dict[str, Any]] = []
            with self._lock:
                for s in self._sessions.values():
                    if s.company_id == company_id and s.agent_id == agent_id:
                        result.append({"session_id": s.session_id,
                                       "ticket_id": s.ticket_id,
                                       "agent_id": s.agent_id, "status": s.status,
                                       "started_at": s.started_at,
                                       "completed_at": s.completed_at,
                                       "stage_reached": s.stage_reached,
                                       "processing_steps": s.processing_steps})
            return result
        except Exception as exc:
            logger.error("get_agent_sessions_failed", company_id=company_id,
                         error=str(exc))
            return []

    def get_handoff_history(self, company_id: str,
                            ticket_id: Optional[str] = None,
                            limit: int = 50) -> List[Dict[str, Any]]:
        """Get handoff records for a company, newest first (BC-001)."""
        try:
            records = self._handoff_records.get(company_id, [])
            if ticket_id:
                records = [r for r in records if r.ticket_id == ticket_id]
            return [{"ticket_id": r.ticket_id, "company_id": r.company_id,
                     "from_agent": r.from_agent, "to_agent": r.to_agent,
                     "handoff_at": r.handoff_at, "reason": r.reason,
                     "context_transferred": r.context_transferred,
                     "success": r.success}
                    for r in reversed(records[-limit:])]
        except Exception as exc:
            logger.error("get_handoff_history_failed", company_id=company_id,
                         error=str(exc))
            return []

    # ── Event Listeners ───────────────────────────────────────────

    def add_event_listener(self, callback: Callable) -> None:
        """Register a callback for notable events. Signature: ``cb(type, payload)``."""
        try:
            if callback not in self._listeners:
                self._listeners.append(callback)
        except Exception as exc:
            logger.error("add_event_listener_failed", error=str(exc))

    def remove_event_listener(self, callback: Callable) -> None:
        """Remove a previously registered event listener."""
        try:
            if callback in self._listeners:
                self._listeners.remove(callback)
        except Exception as exc:
            logger.error("remove_event_listener_failed", error=str(exc))

    # ── Statistics ────────────────────────────────────────────────

    def get_statistics(self, company_id: str) -> Dict[str, Any]:
        """Get session continuity statistics for a company (BC-001).

        Returns lock, session, collision, handoff, and duration metrics.
        """
        try:
            with self._lock:
                active = completed = failed = 0
                agent_counts: Dict[str, int] = defaultdict(int)
                durations: List[float] = []
                for s in self._sessions.values():
                    if s.company_id != company_id:
                        continue
                    if s.status == SessionStatus.ACTIVE.value:
                        active += 1
                        agent_counts[s.agent_id] += 1
                    elif s.status == SessionStatus.COMPLETED.value:
                        completed += 1
                        if s.completed_at:
                            durations.append(
                                (_parse_utc(s.completed_at)
                                 - _parse_utc(s.started_at)).total_seconds())
                    elif s.status == SessionStatus.FAILED.value:
                        failed += 1
                company_locks = sum(
                    1 for k in self._locks if k[0] == company_id)
                company_collisions = len(
                    self._collision_events.get(
                        company_id, []))
                avg_dur = (
                    sum(durations) /
                    len(durations)) if durations else 0.0
                most_active = (max(agent_counts, key=agent_counts.get)
                               if agent_counts else None)
                rate = (company_collisions / self._total_acquire_attempts
                        if self._total_acquire_attempts > 0 else 0.0)
                return {
                    "company_id": company_id,
                    "total_locks_acquired": self._total_locks_acquired,
                    "total_locks_released": self._total_locks_released,
                    "active_locks": company_locks,
                    "total_acquire_attempts": self._total_acquire_attempts,
                    "total_collisions": self._total_collisions,
                    "company_collisions": company_collisions,
                    "collision_rate": round(rate, 4),
                    "active_sessions": active,
                    "completed_sessions": completed,
                    "failed_sessions": failed,
                    "stale_sessions_recovered": self._stale_sessions_recovered,
                    "handoff_count": len(self._handoff_records.get(company_id, [])),
                    "most_active_agent": most_active,
                    "average_session_duration_seconds": round(avg_dur, 2),
                    "agent_counts": dict(agent_counts),
                }
        except Exception as exc:
            logger.error(
                "get_statistics_failed",
                company_id=company_id,
                error=str(exc))
            return {"company_id": company_id, "error": str(exc)}

    # ── Data Management ───────────────────────────────────────────

    def clear_company_data(self, company_id: str) -> Dict[str, Any]:
        """Clear all continuity data for a company — locks, sessions, events, handoffs,
        config.  Use with caution.  Returns ``{success, cleared_counts}`` (BC-001).
        """
        try:
            with self._lock:
                lock_keys = [k for k in self._locks if k[0] == company_id]
                for k in lock_keys:
                    del self._locks[k]
                sid_remove = [sid for sid, s in self._sessions.items()
                              if s.company_id == company_id]
                for sid in sid_remove:
                    s = self._sessions[sid]
                    self._agent_session_counts[s.agent_id] = max(
                        0, self._agent_session_counts.get(s.agent_id, 0) - 1)
                    del self._sessions[sid]
                for k in [
                        k for k in self._ticket_sessions if k[0] == company_id]:
                    self._ticket_sessions.pop(k, None)
                col_n = len(self._collision_events.get(company_id, []))
                hnd_n = len(self._handoff_records.get(company_id, []))
                self._collision_events.pop(company_id, None)
                self._handoff_records.pop(company_id, None)
                self._configs.pop(company_id, None)
                logger.info("company_data_cleared", company_id=company_id,
                            locks=len(lock_keys), sessions=len(sid_remove))
                return {"success": True, "cleared_counts": {
                    "locks": len(lock_keys), "sessions": len(sid_remove),
                    "collision_events": col_n, "handoff_records": hnd_n}}
        except Exception as exc:
            logger.error("clear_company_data_failed", company_id=company_id,
                         error=str(exc))
            return {"success": False, "error": str(exc)}

    # ── Private Helpers ───────────────────────────────────────────

    def _do_acquire(self,
                    key: Tuple[str,
                               str],
                    company_id: str,
                    ticket_id: str,
                    agent_id: str,
                    config: ContinuityConfig,
                    now: str,
                    metadata: Dict[str,
                                   Any]) -> Dict[str,
                                                 Any]:
        """Create and register a new lock (caller must hold self._lock)."""
        self._locks[key] = SessionLock(
            ticket_id=ticket_id,
            company_id=company_id,
            owner_id=agent_id,
            acquired_at=now,
            expires_at=_seconds_from_now(
                config.lock_timeout_seconds),
            status=LockStatus.ACQUIRED.value,
            metadata=metadata)
        self._total_locks_acquired += 1
        logger.info(
            "lock_acquired",
            company_id=company_id,
            ticket_id=ticket_id,
            agent_id=agent_id)
        self._emit_event("lock_acquired",
                         {"company_id": company_id,
                          "ticket_id": ticket_id,
                          "agent_id": agent_id})
        return {"success": True, "lock_status": LockStatus.ACQUIRED.value,
                "action": "acquired"}

    def _resolve_collision(self,
                           existing: SessionLock,
                           contender_id: str,
                           company_id: str,
                           ticket_id: str,
                           config: ContinuityConfig,
                           key: Tuple[str,
                                      str],
                           now: str,
                           metadata: Dict[str,
                                          Any]) -> Dict[str,
                                                        Any]:
        """Apply collision strategy when a lock is contested.

        Strategies — wait: contender retries; preempt: priority-based takeover;
        merge: both proceed (external resolution); reject: immediate reject;
        queue: add to queue.  Caller must hold self._lock.
        """
        self._total_collisions += 1
        strategy = config.collision_strategy
        e_pri = existing.metadata.get("priority", 0)
        c_pri = metadata.get("priority", 0)

        if strategy == CollisionAction.WAIT.value:
            self._record_collision(
                company_id,
                ticket_id,
                existing.owner_id,
                contender_id,
                now,
                CollisionAction.WAIT.value,
                f"Lock held by {
                    existing.owner_id}; " f"contender {contender_id} must wait.")
            return {
                "success": False,
                "lock_status": LockStatus.CONTESTED.value,
                "action": CollisionAction.WAIT.value}

        if strategy == CollisionAction.PREEMPT.value:
            if c_pri > e_pri:
                self._remove_lock(key)
                for sid in self._ticket_sessions.get(key, []):
                    s = self._sessions.get(sid)
                    if s and s.status == SessionStatus.ACTIVE.value:
                        s.status = SessionStatus.PREEMPTED.value
                        s.completed_at = now
                        self._agent_session_counts[s.agent_id] = max(
                            0, self._agent_session_counts.get(s.agent_id, 0) - 1)
                self._record_collision(
                    company_id, ticket_id, existing.owner_id, contender_id, now,
                    CollisionAction.PREEMPT.value,
                    f"Preempted {existing.owner_id} (pri {e_pri}) for "
                    f"{contender_id} (pri {c_pri}).")
                return self._do_acquire(key, company_id, ticket_id,
                                        contender_id, config, now, metadata)
            self._record_collision(
                company_id, ticket_id, existing.owner_id, contender_id, now,
                CollisionAction.WAIT.value,
                f"Contender pri {c_pri} <= existing {e_pri}; must wait.")
            return {
                "success": False,
                "lock_status": LockStatus.CONTESTED.value,
                "action": CollisionAction.WAIT.value}

        if strategy == CollisionAction.MERGE.value:
            self._record_collision(
                company_id,
                ticket_id,
                existing.owner_id,
                contender_id,
                now,
                CollisionAction.MERGE.value,
                f"Merge: {
                    existing.owner_id} and {contender_id} may both proceed.")
            return {"success": True, "lock_status": LockStatus.CONTESTED.value,
                    "action": CollisionAction.MERGE.value,
                    "warning": "Merge mode: resolve conflicts externally."}

        if strategy == CollisionAction.REJECT.value:
            self._record_collision(
                company_id, ticket_id, existing.owner_id, contender_id, now,
                CollisionAction.REJECT.value,
                f"Rejected {contender_id}; lock held by {existing.owner_id}.")
            return {
                "success": False,
                "lock_status": LockStatus.CONTESTED.value,
                "action": CollisionAction.REJECT.value}

        # QUEUE (default / fallback)
        self._record_collision(
            company_id,
            ticket_id,
            existing.owner_id,
            contender_id,
            now,
            CollisionAction.QUEUE.value,
            f"Contender {contender_id} queued; lock held by {
                existing.owner_id}.")
        return {"success": False, "lock_status": LockStatus.CONTESTED.value,
                "action": CollisionAction.QUEUE.value}

    def _record_collision(self, company_id: str, ticket_id: str,
                          existing_owner: str, contender_id: str,
                          detected_at: str, action_taken: str,
                          resolution: str) -> Dict[str, str]:
        """Record a collision event. Returns summary dict with event_id."""
        self._collision_events[company_id].append(CollisionEvent(
            ticket_id=ticket_id, company_id=company_id,
            existing_owner=existing_owner, contender_id=contender_id,
            detected_at=detected_at, action_taken=action_taken,
            resolution=resolution))
        if len(self._collision_events[company_id]
               ) > self._max_collision_events:
            self._collision_events[company_id] = (
                self._collision_events[company_id][-self._max_collision_events:])
        logger.warning("collision_detected", company_id=company_id,
                       ticket_id=ticket_id, action_taken=action_taken)
        return {"event_id": str(uuid.uuid4()), "action_taken": action_taken,
                "resolution": resolution}

    def _remove_lock(self, key: Tuple[str, str]) -> None:
        """Remove a lock from registry (caller must hold self._lock)."""
        self._locks.pop(key, None)

    def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Fire all registered listeners. Never raises."""
        try:
            for listener in list(self._listeners):
                try:
                    listener(event_type, payload)
                except Exception as exc:
                    logger.debug(
                        "session_continuity_listener_failed",
                        event_type=event_type,
                        error=str(exc))
        except Exception as exc:
            logger.debug(
                "session_continuity_emit_failed",
                event_type=event_type,
                error=str(exc))


# ── Module-level singleton ────────────────────────────────────────────

_session_continuity_manager: Optional[SessionContinuityManager] = None


def get_session_continuity_manager() -> SessionContinuityManager:
    """Get or create the SessionContinuityManager singleton."""
    global _session_continuity_manager
    if _session_continuity_manager is None:
        _session_continuity_manager = SessionContinuityManager()
    return _session_continuity_manager
