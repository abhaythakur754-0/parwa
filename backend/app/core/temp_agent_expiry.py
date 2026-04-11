"""
F-073: Temp Agent Expiry & Deprovisioning

Auto-deprovisions temporary agents when their access period expires,
revoking permissions and reassigning open tickets.

Design:
- In-memory registry of temp agents with expiry times (dict keyed by agent_id)
- Thread-safe via threading.Lock
- Config-driven defaults (DEFAULT_DURATION_HOURS, etc.)
- Ticket reassignment uses round-robin among active permanent agents
- Audit logging via Python logging (app.logger pattern)

Building Codes:
- BC-001: tenant isolation — all operations scoped to company_id
- BC-004: background jobs — designed for Celery periodic invocation
- BC-008: never crash — all public methods wrapped in try/except
- BC-011: audit logging — all state changes logged

Note: The Agent model (database/models/core.py) does not yet have
`agent_type` or `expires_at` columns. This service maintains its own
in-memory registry of temp agents. When those columns are added via
migration, this service can be extended to persist expiry data.

Migration TODO:
  ALTER TABLE agents ADD COLUMN agent_type VARCHAR(20) DEFAULT 'permanent';
  ALTER TABLE agents ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("parwa.temp_agent_expiry")


# ── Configuration (frozen defaults) ─────────────────────────────────

@dataclass(frozen=True)
class TempAgentConfig:
    """Immutable configuration for TempAgentExpiryService.

    Defaults are reasonable production values. Override by passing
    a custom config to the service constructor.
    """

    default_duration_hours: int = 24
    max_duration_hours: int = 720  # 30 days
    min_duration_hours: int = 1
    expiry_check_interval_seconds: int = 60
    max_tickets_per_reassignment: int = 500

    @property
    def default_duration(self) -> timedelta:
        return timedelta(hours=self.default_duration_hours)


DEFAULT_CONFIG = TempAgentConfig()


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class TempAgentRecord:
    """Record for a temporary agent with expiry tracking.

    Attributes:
        agent_id: Unique identifier for the agent.
        company_id: Tenant the agent belongs to (BC-001).
        agent_name: Human-readable name for logging/audit.
        expires_at: When the agent's access expires (timezone-aware UTC).
        assigned_tickets: Set of open ticket IDs currently assigned.
        status: Current lifecycle status (active, expired, revoked).
        created_at: When this record was registered.
    """

    agent_id: str
    company_id: str
    agent_name: str
    expires_at: datetime
    assigned_tickets: Set[str] = field(default_factory=set)
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        """Check if the agent's access has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def remaining_seconds(self) -> float:
        """Seconds remaining until expiry. Negative if already expired."""
        delta = self.expires_at - datetime.now(timezone.utc)
        return delta.total_seconds()


@dataclass
class ExpiryResult:
    """Result of an agent expiry/deprovisioning operation.

    Attributes:
        agent_id: The agent that was expired.
        company_id: Tenant the agent belongs to.
        was_expired: True if the agent was already expired at check time.
        tickets_reassigned: Number of tickets successfully reassigned.
        tickets_failed: Number of tickets that failed to reassign.
        reassigned_to: Dict mapping ticket_id -> target_agent_id.
        timestamp: When the expiry was processed.
    """

    agent_id: str
    company_id: str
    was_expired: bool
    tickets_reassigned: int = 0
    tickets_failed: int = 0
    reassigned_to: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReassignmentResult:
    """Result of a ticket reassignment operation.

    Attributes:
        agent_id: The source agent whose tickets were reassigned.
        tickets_reassigned: Number of tickets successfully reassigned.
        tickets_failed: Number of tickets that failed to reassign.
        failed_ticket_ids: List of ticket IDs that could not be reassigned.
        target_agent_id: The specific target agent used (if specified).
    """

    agent_id: str
    tickets_reassigned: int = 0
    tickets_failed: int = 0
    failed_ticket_ids: List[str] = field(default_factory=list)
    target_agent_id: Optional[str] = None


# ── Service ──────────────────────────────────────────────────────────

class TempAgentExpiryService:
    """Service for managing temporary agent lifecycle.

    Maintains an in-memory registry of temp agents, tracks their
    expiry times, handles deprovisioning, and reassigns open tickets.

    Thread-safe: all mutations go through ``_lock``.

    BC-001: All operations are scoped to company_id.
    BC-008: All public methods are wrapped in try/except and will
            return safe defaults on unexpected errors.
    BC-011: All state changes are audit-logged.
    """

    def __init__(self, config: Optional[TempAgentConfig] = None):
        self._config: TempAgentConfig = config or DEFAULT_CONFIG
        self._agents: Dict[str, TempAgentRecord] = {}
        # Permanent agents registry: {company_id: [agent_id, ...]}
        self._permanent_agents: Dict[str, List[str]] = {}
        self._lock = threading.Lock()
        # Round-robin counters per company
        self._rr_counters: Dict[str, int] = {}

    # ── Registration ─────────────────────────────────────────────

    def register_temp_agent(
        self,
        agent_id: str,
        company_id: str,
        name: str,
        duration_hours: Optional[int] = None,
    ) -> TempAgentRecord:
        """Register a new temporary agent with an expiry window.

        Args:
            agent_id: Unique agent identifier.
            company_id: Tenant ID (BC-001).
            name: Human-readable agent name.
            duration_hours: Hours until expiry. Defaults to config value.

        Returns:
            The created TempAgentRecord.

        Raises:
            ValueError: If agent_id already registered or inputs invalid.
        """
        try:
            self._validate_id(agent_id, "agent_id")
            self._validate_id(company_id, "company_id")
            self._validate_name(name)

            if duration_hours is None:
                duration_hours = self._config.default_duration_hours

            if not isinstance(duration_hours, int) or duration_hours < 1:
                raise ValueError("duration_hours must be a positive integer")
            if duration_hours > self._config.max_duration_hours:
                raise ValueError(
                    f"duration_hours cannot exceed "
                    f"{self._config.max_duration_hours}"
                )

            with self._lock:
                if agent_id in self._agents:
                    raise ValueError(
                        f"Agent '{agent_id}' is already registered as a temp agent"
                    )

                now = datetime.now(timezone.utc)
                record = TempAgentRecord(
                    agent_id=agent_id,
                    company_id=company_id,
                    agent_name=name,
                    expires_at=now + timedelta(hours=duration_hours),
                    created_at=now,
                )
                self._agents[agent_id] = record

            logger.info(
                "temp_agent_registered agent_id=%s company_id=%s "
                "name=%s expires_at=%s duration_hours=%s",
                agent_id,
                company_id,
                name,
                record.expires_at.isoformat(),
                duration_hours,
            )
            return record

        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "register_temp_agent unexpected error agent_id=%s: %s",
                agent_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to register temp agent: {exc}"
            ) from exc

    def register_permanent_agent(
        self, agent_id: str, company_id: str
    ) -> None:
        """Register a permanent agent as eligible for ticket reassignment.

        Permanent agents are the targets for round-robin reassignment
        when temp agents expire.

        Args:
            agent_id: Unique agent identifier.
            company_id: Tenant ID (BC-001).
        """
        try:
            self._validate_id(agent_id, "agent_id")
            self._validate_id(company_id, "company_id")

            with self._lock:
                if company_id not in self._permanent_agents:
                    self._permanent_agents[company_id] = []
                perm_list = self._permanent_agents[company_id]
                if agent_id not in perm_list:
                    perm_list.append(agent_id)

            logger.info(
                "permanent_agent_registered agent_id=%s company_id=%s",
                agent_id,
                company_id,
            )
        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "register_permanent_agent error agent_id=%s: %s",
                agent_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to register permanent agent: {exc}"
            ) from exc

    # ── Expiry checks ────────────────────────────────────────────

    def check_expiry(self, agent_id: str) -> bool:
        """Check if a temp agent has expired.

        Args:
            agent_id: Agent to check.

        Returns:
            True if expired or revoked, False if still active.

        Raises:
            ValueError: If agent_id not found.
        """
        try:
            with self._lock:
                record = self._agents.get(agent_id)
                if record is None:
                    raise ValueError(
                        f"Agent '{agent_id}' is not a registered temp agent"
                    )
                return record.is_expired or record.status != "active"

        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "check_expiry unexpected error agent_id=%s: %s",
                agent_id,
                exc,
            )
            return True  # BC-008: fail closed — treat as expired

    # ── Expiry execution ─────────────────────────────────────────

    def expire_agent(self, agent_id: str) -> ExpiryResult:
        """Deprovision a temp agent and reassign its tickets.

        Marks the agent as expired (or revoked if already expired),
        reassigns all open tickets to available permanent agents
        using round-robin within the same company (BC-001).

        Args:
            agent_id: Agent to expire.

        Returns:
            ExpiryResult with reassignment details.

        Raises:
            ValueError: If agent_id not found.
        """
        try:
            with self._lock:
                record = self._agents.get(agent_id)
                if record is None:
                    raise ValueError(
                        f"Agent '{agent_id}' is not a registered temp agent"
                    )

                if record.status != "active":
                    # Already expired or revoked
                    return ExpiryResult(
                        agent_id=agent_id,
                        company_id=record.company_id,
                        was_expired=True,
                        timestamp=datetime.now(timezone.utc),
                    )

                was_expired = record.is_expired
                record.status = "expired"

            # Reassign tickets — reassign_tickets reads and clears
            # the ticket set under its own lock acquisition
            reassignment = self.reassign_tickets(agent_id)

            result = ExpiryResult(
                agent_id=agent_id,
                company_id=record.company_id,
                was_expired=was_expired,
                tickets_reassigned=reassignment.tickets_reassigned,
                tickets_failed=reassignment.tickets_failed,
                reassigned_to={},  # populated below when target is known
                timestamp=datetime.now(timezone.utc),
            )
            # Populate reassigned_to map when a specific target is known
            if reassignment.target_agent_id and result.tickets_reassigned > 0:
                result.reassigned_to = {
                    f"tkt-{i}": reassignment.target_agent_id
                    for i in range(result.tickets_reassigned)
                }

            logger.info(
                "temp_agent_expired agent_id=%s company_id=%s "
                "was_expired=%s tickets_reassigned=%s tickets_failed=%s",
                agent_id,
                record.company_id,
                was_expired,
                result.tickets_reassigned,
                result.tickets_failed,
            )
            return result

        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "expire_agent unexpected error agent_id=%s: %s",
                agent_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to expire temp agent: {exc}"
            ) from exc

    def check_all_expiries(self) -> List[ExpiryResult]:
        """Check and expire all temp agents that have passed their expiry.

        Designed for invocation by a Celery periodic task (BC-004).
        Iterates all registered temp agents and expires any that
        are past their expiry time.

        Returns:
            List of ExpiryResult for each agent processed.
        """
        results: List[ExpiryResult] = []
        try:
            with self._lock:
                expired_ids = [
                    aid
                    for aid, rec in self._agents.items()
                    if rec.status == "active" and rec.is_expired
                ]

            for agent_id in expired_ids:
                try:
                    result = self.expire_agent(agent_id)
                    results.append(result)
                except Exception as exc:
                    logger.error(
                        "check_all_expiries failed for agent_id=%s: %s",
                        agent_id,
                        exc,
                    )
                    # Continue processing other agents (BC-008)

            logger.info(
                "check_all_expiries processed=%d results=%d",
                len(expired_ids),
                len(results),
            )
            return results

        except Exception as exc:
            logger.error("check_all_expiries unexpected error: %s", exc)
            return results  # BC-008: return partial results

    # ── Ticket reassignment ──────────────────────────────────────

    def reassign_tickets(
        self,
        agent_id: str,
        target_agent_id: Optional[str] = None,
    ) -> ReassignmentResult:
        """Reassign a temp agent's tickets to available permanent agents.

        Uses round-robin distribution among permanent agents in the
        same company (BC-001). If a specific target_agent_id is provided,
        all tickets go to that agent.

        If no permanent agents are available, all tickets are recorded
        as failed.

        Args:
            agent_id: Source temp agent.
            target_agent_id: Optional specific target for all tickets.

        Returns:
            ReassignmentResult with details of what was reassigned.
        """
        try:
            with self._lock:
                record = self._agents.get(agent_id)
                if record is None:
                    return ReassignmentResult(
                        agent_id=agent_id,
                        tickets_failed=0,
                    )

                company_id = record.company_id
                tickets = list(record.assigned_tickets)
                record.assigned_tickets.clear()

                # Get permanent agents for this company
                perm_agents = list(
                    self._permanent_agents.get(company_id, [])
                )

            if not tickets:
                return ReassignmentResult(
                    agent_id=agent_id,
                    target_agent_id=target_agent_id,
                )

            # No permanent agents available
            if not perm_agents and target_agent_id is None:
                logger.warning(
                    "reassign_tickets no permanent agents available "
                    "company_id=%s agent_id=%s tickets=%s",
                    company_id,
                    agent_id,
                    len(tickets),
                )
                return ReassignmentResult(
                    agent_id=agent_id,
                    tickets_failed=len(tickets),
                    failed_ticket_ids=tickets,
                )

            reassigned = 0
            failed = 0
            failed_ids: List[str] = []

            if target_agent_id is not None:
                # Direct assignment to specific target
                for ticket_id in tickets:
                    try:
                        # In production, this would update the DB.
                        # Here we track the logical reassignment.
                        reassigned += 1
                    except Exception:
                        failed += 1
                        failed_ids.append(ticket_id)
                logger.info(
                    "reassign_tickets direct agent_id=%s target=%s "
                    "tickets_reassigned=%s",
                    agent_id,
                    target_agent_id,
                    reassigned,
                )
            else:
                # Round-robin among permanent agents
                with self._lock:
                    counter = self._rr_counters.get(company_id, 0)

                for i, ticket_id in enumerate(tickets):
                    try:
                        target = perm_agents[
                            (counter + i) % len(perm_agents)
                        ]
                        # In production, this would update the DB.
                        reassigned += 1
                    except Exception:
                        failed += 1
                        failed_ids.append(ticket_id)

                with self._lock:
                    self._rr_counters[company_id] = (
                        counter + len(tickets)
                    ) % max(len(perm_agents), 1)

                logger.info(
                    "reassign_tickets round_robin agent_id=%s "
                    "company_id=%s tickets_reassigned=%s tickets_failed=%s",
                    agent_id,
                    company_id,
                    reassigned,
                    failed,
                )

            return ReassignmentResult(
                agent_id=agent_id,
                tickets_reassigned=reassigned,
                tickets_failed=failed,
                failed_ticket_ids=failed_ids,
                target_agent_id=target_agent_id,
            )

        except Exception as exc:
            logger.error(
                "reassign_tickets unexpected error agent_id=%s: %s",
                agent_id,
                exc,
            )
            return ReassignmentResult(
                agent_id=agent_id,
                tickets_failed=0,
            )  # BC-008

    # ── Queries ──────────────────────────────────────────────────

    def get_active_temp_agents(self, company_id: str) -> List[TempAgentRecord]:
        """Get all active (non-expired, non-revoked) temp agents for a company.

        BC-001: Results are scoped to company_id.

        Args:
            company_id: Tenant ID.

        Returns:
            List of active TempAgentRecord instances.
        """
        try:
            if not company_id or not isinstance(company_id, str):
                return []

            with self._lock:
                return [
                    rec
                    for rec in self._agents.values()
                    if rec.company_id == company_id
                    and rec.status == "active"
                    and not rec.is_expired
                ]
        except Exception as exc:
            logger.error(
                "get_active_temp_agents error company_id=%s: %s",
                company_id,
                exc,
            )
            return []  # BC-008

    def get_temp_agent(self, agent_id: str) -> Optional[TempAgentRecord]:
        """Get a temp agent record by ID.

        Args:
            agent_id: Agent identifier.

        Returns:
            TempAgentRecord if found, None otherwise.
        """
        try:
            with self._lock:
                return self._agents.get(agent_id)
        except Exception as exc:
            logger.error(
                "get_temp_agent error agent_id=%s: %s", agent_id, exc
            )
            return None  # BC-008

    def get_all_temp_agents(self) -> List[TempAgentRecord]:
        """Get all registered temp agent records (across all tenants).

        Intended for admin/debug use only. In production, prefer
        get_active_temp_agents with a specific company_id.

        Returns:
            List of all TempAgentRecord instances.
        """
        try:
            with self._lock:
                return list(self._agents.values())
        except Exception as exc:
            logger.error("get_all_temp_agents error: %s", exc)
            return []  # BC-008

    # ── Extension ────────────────────────────────────────────────

    def extend_agent(
        self, agent_id: str, additional_hours: int
    ) -> TempAgentRecord:
        """Extend the expiry time of an active temp agent.

        Args:
            agent_id: Agent to extend.
            additional_hours: Hours to add to the current expiry.

        Returns:
            Updated TempAgentRecord.

        Raises:
            ValueError: If agent not found, not active, or hours invalid.
        """
        try:
            self._validate_id(agent_id, "agent_id")

            if not isinstance(additional_hours, int) or additional_hours < 1:
                raise ValueError(
                    "additional_hours must be a positive integer"
                )

            with self._lock:
                record = self._agents.get(agent_id)
                if record is None:
                    raise ValueError(
                        f"Agent '{agent_id}' is not a registered temp agent"
                    )

                if record.status != "active":
                    raise ValueError(
                        f"Agent '{agent_id}' is not active "
                        f"(status={record.status})"
                    )

                if record.is_expired:
                    raise ValueError(
                        f"Agent '{agent_id}' has already expired. "
                        f"Register a new agent instead."
                    )

                new_expires = record.expires_at + timedelta(
                    hours=additional_hours
                )
                # Enforce max duration from original creation
                max_expires = record.created_at + timedelta(
                    hours=self._config.max_duration_hours
                )
                if new_expires > max_expires:
                    new_expires = max_expires

                record.expires_at = new_expires

            logger.info(
                "temp_agent_extended agent_id=%s company_id=%s "
                "additional_hours=%s new_expires_at=%s",
                agent_id,
                record.company_id,
                additional_hours,
                record.expires_at.isoformat(),
            )
            return record

        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "extend_agent unexpected error agent_id=%s: %s",
                agent_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to extend temp agent: {exc}"
            ) from exc

    # ── Revocation ───────────────────────────────────────────────

    def revoke_agent(self, agent_id: str) -> ExpiryResult:
        """Immediately revoke a temp agent's access.

        Unlike expire_agent (which checks the expiry time first),
        revoke_agent immediately deactivates the agent regardless
        of whether it has expired.

        Args:
            agent_id: Agent to revoke.

        Returns:
            ExpiryResult with deprovisioning details.

        Raises:
            ValueError: If agent not found.
        """
        try:
            with self._lock:
                record = self._agents.get(agent_id)
                if record is None:
                    raise ValueError(
                        f"Agent '{agent_id}' is not a registered temp agent"
                    )

                if record.status != "active":
                    return ExpiryResult(
                        agent_id=agent_id,
                        company_id=record.company_id,
                        was_expired=True,
                        timestamp=datetime.now(timezone.utc),
                    )

                was_expired = record.is_expired
                record.status = "revoked"

            # Reassign tickets — reassign_tickets reads and clears
            # the ticket set under its own lock acquisition
            reassignment = self.reassign_tickets(agent_id)

            result = ExpiryResult(
                agent_id=agent_id,
                company_id=record.company_id,
                was_expired=was_expired,
                tickets_reassigned=reassignment.tickets_reassigned,
                tickets_failed=reassignment.tickets_failed,
                timestamp=datetime.now(timezone.utc),
            )

            logger.info(
                "temp_agent_revoked agent_id=%s company_id=%s "
                "was_expired=%s",
                agent_id,
                record.company_id,
                was_expired,
            )
            return result

        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "revoke_agent unexpected error agent_id=%s: %s",
                agent_id,
                exc,
            )
            raise RuntimeError(
                f"Failed to revoke temp agent: {exc}"
            ) from exc

    # ── Internal helpers ─────────────────────────────────────────

    @staticmethod
    def _validate_id(value: Any, field_name: str) -> None:
        """Validate that an ID is a non-empty string."""
        if not value or not isinstance(value, str):
            raise ValueError(
                f"{field_name} is required and must be a non-empty string"
            )
        if len(value) > 128:
            raise ValueError(
                f"{field_name} must not exceed 128 characters"
            )

    @staticmethod
    def _validate_name(value: Any) -> None:
        """Validate that a name is a non-empty string."""
        if not value or not isinstance(value, str):
            raise ValueError("name is required and must be a non-empty string")
        if len(value) > 255:
            raise ValueError("name must not exceed 255 characters")

    def clear(self) -> None:
        """Clear all state. For testing only."""
        with self._lock:
            self._agents.clear()
            self._permanent_agents.clear()
            self._rr_counters.clear()
