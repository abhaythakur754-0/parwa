"""
Ticket Assignment Engine — Score-based AI + Rule-based fallback + Hybrid.

PARWA SaaS — Intelligent ticket routing to the best-fit support agent.

Scoring weights:
    specialty_match = 40%
    workload        = 30%
    accuracy        = 20%
    jitter          = 10%

Assignment strategies:
    - SCORE_BASED  : Pure ML-style weighted scoring (best agent by composite score).
    - RULE_BASED   : Deterministic round-robin with priority escalation.
    - HYBRID       : Score-based first; falls back to rule-based when the best
                      score is below a configurable threshold.

All public methods are ``async`` so the engine integrates cleanly into
asyncio web-frameworks (FastAPI, Starlette, aiohttp) and async task queues.

Redis integration is **optional** — pass ``redis_client=None`` (default)
to run entirely in-process with in-memory state.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AssignmentStrategy(Enum):
    """Supported assignment routing strategies."""
    SCORE_BASED = "score_based"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"


class AgentStatus(Enum):
    """Agent availability states."""
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    BUSY = "busy"


class TicketPriority(Enum):
    """Canonical priority levels — lower ordinal ⇒ higher priority."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChannelType(Enum):
    """Supported inbound channels."""
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"
    SOCIAL = "social"
    PORTAL = "portal"
    API = "api"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AgentProfile:
    """Immutable view of a support agent at a point in time."""

    agent_id: str
    name: str
    email: str
    specialties: List[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.ONLINE
    is_online: bool = True
    max_concurrent: int = 5
    current_load: int = 0
    accuracy_score: float = 0.95
    avg_response_time: float = 300.0
    assigned_count: int = 0
    last_assigned: Optional[datetime] = None
    timezone_str: str = "UTC"
    seniority_years: float = 0.0
    languages: List[str] = field(default_factory=lambda: ["en"])
    customer_tier_access: List[str] = field(
        default_factory=lambda: [
            "standard", "premium", "enterprise"])
    shift_start: Optional[str] = None  # HH:MM in agent timezone
    shift_end: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- derived helpers --

    @property
    def available_capacity(self) -> int:
        """Remaining concurrent slots."""
        return max(0, self.max_concurrent - self.current_load)

    @property
    def utilization_ratio(self) -> float:
        """0..1 fraction of capacity consumed."""
        if self.max_concurrent <= 0:
            return 1.0
        return min(1.0, self.current_load / self.max_concurrent)

    @property
    def can_accept(self) -> bool:
        """Agent is online *and* has at least one free slot."""
        return self.is_online and self.available_capacity > 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict (useful for JSON APIs / caching)."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "email": self.email,
            "specialties": self.specialties,
            "status": self.status.value,
            "is_online": self.is_online,
            "max_concurrent": self.max_concurrent,
            "current_load": self.current_load,
            "accuracy_score": self.accuracy_score,
            "avg_response_time": self.avg_response_time,
            "assigned_count": self.assigned_count,
            "last_assigned": self.last_assigned.isoformat() if self.last_assigned else None,
            "available_capacity": self.available_capacity,
            "utilization_ratio": round(
                self.utilization_ratio,
                4),
        }


@dataclass
class TicketContext:
    """Rich context for an inbound ticket."""

    ticket_id: str
    subject: str
    description: str
    category: str = "general"
    priority: str = "medium"
    customer_tier: str = "standard"
    tags: List[str] = field(default_factory=list)
    language: str = "en"
    channel: str = "email"
    customer_id: Optional[str] = None
    customer_region: Optional[str] = None
    created_at: Optional[str] = None
    estimated_complexity: float = 0.5  # 0..1
    sla_deadline: Optional[str] = None
    previous_agent_id: Optional[str] = None  # for follow-up routing
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def priority_enum(self) -> TicketPriority:
        try:
            return TicketPriority(self.priority.lower())
        except ValueError:
            return TicketPriority.MEDIUM

    @property
    def channel_enum(self) -> ChannelType:
        try:
            return ChannelType(self.channel.lower())
        except ValueError:
            return ChannelType.EMAIL

    @property
    def search_terms(self) -> Set[str]:
        """Normalised bag-of-words from subject + tags."""
        terms: Set[str] = set()
        for word in self.subject.lower().split():
            terms.add(word)
        for tag in self.tags:
            terms.add(tag.lower())
        for word in self.category.lower().split("_"):
            terms.add(word)
        return terms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "subject": self.subject,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "customer_tier": self.customer_tier,
            "tags": self.tags,
            "language": self.language,
            "channel": self.channel,
            "customer_id": self.customer_id,
            "customer_region": self.customer_region,
            "created_at": self.created_at,
            "estimated_complexity": self.estimated_complexity,
            "sla_deadline": self.sla_deadline,
            "previous_agent_id": self.previous_agent_id,
        }


@dataclass
class AssignmentResult:
    """Outcome of a single ticket assignment."""

    ticket_id: str
    assigned_to: str  # NOTE: key is "assigned_to" not "agent_type"
    strategy: str
    score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    timestamp: str = ""
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def is_unassigned(self) -> bool:
        return self.assigned_to == "unassigned"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "assigned_to": self.assigned_to,
            "strategy": self.strategy,
            "score": round(self.score, 6),
            "score_breakdown": self.score_breakdown,
            "alternatives": self.alternatives,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "latency_ms": round(self.latency_ms, 2),
            "is_unassigned": self.is_unassigned,
        }


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------

class BaseAssigner(ABC):
    """Abstract base for all ticket assignment strategies.

    Subclasses must implement ``assign`` and ``batch_assign``.  A default
    ``batch_assign`` that simply loops over tickets is provided as a
    convenience — subclasses may override it with more efficient batch logic.
    """

    @abstractmethod
    async def assign(
        self,
        ticket: TicketContext,
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> AssignmentResult:
        """Assign *ticket* to the single best agent from *agents*."""
        ...

    @abstractmethod
    async def batch_assign(
        self,
        tickets: List[TicketContext],
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> List[AssignmentResult]:
        """Assign multiple tickets.  Order of results matches *tickets*."""
        ...


# ---------------------------------------------------------------------------
# Rule-Based Assigner (round-robin + priority escalation)
# ---------------------------------------------------------------------------

class RuleBasedAssigner(BaseAssigner):
    """Deterministic round-robin assignment with priority-aware escalation.

    Behaviour
    ---------
    * Available agents are filtered by ``is_online`` and free capacity.
    * If no agents are available, the full pool is used as a fallback.
    * High-priority tickets skip the queue and are assigned immediately to
      the least-loaded available agent.
    * ``previous_agent_id`` on the ticket enables follow-up routing to
      the same agent (if still available).
    """

    def __init__(self, redis_client: Any = None) -> None:
        self.redis = redis_client
        self._counters: Dict[str, int] = {}
        self._assignment_log: List[Dict[str, Any]] = []

    # -- helpers --

    def _available_agents(
        self, agents: List[AgentProfile], ticket: TicketContext
    ) -> List[AgentProfile]:
        """Filter and sort agents for rule-based eligibility."""
        available = [
            a for a in agents
            if a.is_online and a.available_capacity > 0
        ]
        # Prefer agents with matching language
        if ticket.language:
            lang_match = [
                a for a in available if ticket.language in a.languages]
            if lang_match:
                available = lang_match
        return available

    def _least_loaded(
            self,
            agents: List[AgentProfile]) -> Optional[AgentProfile]:
        """Return the agent with the lowest current_load (ties broken by last_assigned)."""
        if not agents:
            return None
        return min(
            agents,
            key=lambda a: (
                a.current_load,
                a.last_assigned or datetime.min.replace(
                    tzinfo=timezone.utc)),
        )

    # -- public API --

    async def assign(
        self,
        ticket: TicketContext,
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> AssignmentResult:
        start = time.monotonic()

        # Follow-up routing: reuse previous agent if available
        if ticket.previous_agent_id:
            prev = next((a for a in agents if a.agent_id
                         == ticket.previous_agent_id and a.can_accept), None, )
            if prev is not None:
                elapsed_ms = (time.monotonic() - start) * 1000
                result = AssignmentResult(
                    ticket_id=ticket.ticket_id,
                    assigned_to=prev.agent_id,
                    strategy="rule_based",
                    score=1.0,
                    reason=f"Follow-up routing to {prev.name} (previous assignee)",
                    latency_ms=elapsed_ms,
                )
                self._assignment_log.append(result.to_dict())
                return result

        # Priority escalation: critical/high tickets go to least-loaded
        if ticket.priority_enum in (
                TicketPriority.CRITICAL,
                TicketPriority.HIGH):
            pool = self._available_agents(agents, ticket)
            if not pool:
                pool = agents
            best = self._least_loaded(pool)
            if best is not None:
                elapsed_ms = (time.monotonic() - start) * 1000
                result = AssignmentResult(
                    ticket_id=ticket.ticket_id,
                    assigned_to=best.agent_id,
                    strategy="rule_based",
                    score=1.0,
                    reason=f"Priority escalation → least-loaded agent {best.name} (load={best.current_load})",
                    latency_ms=elapsed_ms,
                )
                self._assignment_log.append(result.to_dict())
                return result

        # Standard round-robin
        available = self._available_agents(agents, ticket)
        if not available:
            available = agents  # fallback to all
        if not available:
            elapsed_ms = (time.monotonic() - start) * 1000
            return AssignmentResult(
                ticket_id=ticket.ticket_id,
                assigned_to="unassigned",
                strategy="rule_based",
                reason="No agents available",
                latency_ms=elapsed_ms,
            )

        key = ticket.category
        idx = self._counters.get(key, 0) % len(available)
        assigned = available[idx]
        self._counters[key] = idx + 1

        elapsed_ms = (time.monotonic() - start) * 1000
        result = AssignmentResult(
            ticket_id=ticket.ticket_id,
            assigned_to=assigned.agent_id,
            strategy="rule_based",
            score=1.0,
            reason=f"Round-robin assignment to {assigned.name}",
            latency_ms=elapsed_ms,
        )
        self._assignment_log.append(result.to_dict())
        return result

    async def batch_assign(
        self,
        tickets: List[TicketContext],
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> List[AssignmentResult]:
        results: List[AssignmentResult] = []
        for ticket in tickets:
            result = await self.assign(ticket, agents, **kwargs)
            results.append(result)
        return results

    def get_assignment_log(self) -> List[Dict[str, Any]]:
        """Return a shallow copy of the internal assignment log."""
        return list(self._assignment_log)

    def reset_counters(self) -> None:
        """Clear round-robin counters and the log."""
        self._counters.clear()
        self._assignment_log.clear()


# ---------------------------------------------------------------------------
# Score-Based Assigner (ML-style weighted scoring)
# ---------------------------------------------------------------------------

class ScoreBasedAssigner(BaseAssigner):
    """ML-score based assignment.

    Weighted composite score:
        specialty_match  = 40 %
        workload         = 30 %
        accuracy         = 20 %
        jitter           = 10 %

    The jitter component adds a small random perturbation to break ties
    and inject diversity, preventing all tickets from piling on a single
    agent.
    """

    def __init__(
        self,
        redis_client: Any = None,
        jitter_range: float = 0.05,
    ) -> None:
        self.redis = redis_client
        self.jitter_range = jitter_range
        self._weights: Dict[str, float] = {
            "specialty": 0.40,
            "workload": 0.30,
            "accuracy": 0.20,
            "jitter": 0.10,
        }
        self._score_cache: Dict[str, Tuple[float, Dict[str, float]]] = {}

    # -- scoring components --

    def _specialty_score(
        self, agent: AgentProfile, ticket: TicketContext
    ) -> float:
        """0..1 — higher when the agent's specialties match the ticket."""
        if not agent.specialties:
            return 0.30  # baseline for generalists

        search_terms = ticket.search_terms
        match_count = 0
        for spec in agent.specialties:
            spec_lower = spec.lower()
            if spec_lower in search_terms:
                match_count += 1
            elif spec_lower in ticket.category.lower():
                match_count += 1

        return min(1.0, 0.30 + match_count * 0.35)

    def _workload_score(self, agent: AgentProfile) -> float:
        """0..1 — higher when the agent has more free capacity."""
        if agent.max_concurrent <= 0:
            return 0.0
        ratio = agent.current_load / agent.max_concurrent
        return max(0.0, 1.0 - ratio)

    def _accuracy_score(self, agent: AgentProfile) -> float:
        """0..1 — direct mapping from the agent's historical accuracy."""
        return min(1.0, max(0.0, agent.accuracy_score))

    def _jitter_score(self) -> float:
        """0..jitter_range — random noise for tie-breaking."""
        return random.uniform(0.0, self.jitter_range)

    def _seniority_bonus(
            self,
            agent: AgentProfile,
            ticket: TicketContext) -> float:
        """Small bonus (0..0.05) for senior agents on complex tickets."""
        if ticket.estimated_complexity < 0.5:
            return 0.0
        return min(0.05, agent.seniority_years * 0.01)

    def _language_bonus(
            self,
            agent: AgentProfile,
            ticket: TicketContext) -> float:
        """0..0.10 bonus when the agent speaks the ticket's language."""
        if not ticket.language or ticket.language == "en":
            return 0.0
        if ticket.language in agent.languages:
            return 0.10
        return 0.0

    def _tier_access_score(
            self,
            agent: AgentProfile,
            ticket: TicketContext) -> float:
        """1.0 if the agent is authorised for the customer tier, 0.2 otherwise."""
        if ticket.customer_tier in agent.customer_tier_access:
            return 1.0
        return 0.2

    # -- composite score --

    def _calculate_score(
        self, agent: AgentProfile, ticket: TicketContext
    ) -> Tuple[float, Dict[str, float]]:
        """Return (total_score, breakdown_dict)."""
        spec = self._specialty_score(agent, ticket)
        work = self._workload_score(agent)
        acc = self._accuracy_score(agent)
        jit = self._jitter_score()
        seniority = self._seniority_bonus(agent, ticket)
        lang = self._language_bonus(agent, ticket)
        tier = self._tier_access_score(agent, ticket)

        total = (
            spec * self._weights["specialty"]
            + work * self._weights["workload"]
            + acc * self._weights["accuracy"]
            + jit * self._weights["jitter"]
            + seniority
            + lang
            + tier * 0.05
        )
        total = min(1.0, total)  # clamp

        breakdown: Dict[str, float] = {
            "specialty": round(spec, 6),
            "workload": round(work, 6),
            "accuracy": round(acc, 6),
            "jitter": round(jit, 6),
            "seniority_bonus": round(seniority, 6),
            "language_bonus": round(lang, 6),
            "tier_access": round(tier * 0.05, 6),
            "total": round(total, 6),
        }
        return total, breakdown

    # -- public API --

    async def assign(
        self,
        ticket: TicketContext,
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> AssignmentResult:
        start = time.monotonic()

        if not agents:
            elapsed_ms = (time.monotonic() - start) * 1000
            return AssignmentResult(
                ticket_id=ticket.ticket_id,
                assigned_to="unassigned",
                strategy="score_based",
                reason="No agents available",
                latency_ms=elapsed_ms,
            )

        scored: List[Tuple[AgentProfile, float, Dict[str, float]]] = []
        for agent in agents:
            cache_key = f"{agent.agent_id}:{ticket.ticket_id}"
            if cache_key in self._score_cache:
                score_val, breakdown = self._score_cache[cache_key]
            else:
                score_val, breakdown = self._calculate_score(agent, ticket)
                self._score_cache[cache_key] = (score_val, breakdown)
            scored.append((agent, score_val, breakdown))

        scored.sort(key=lambda x: x[1], reverse=True)
        best_agent, best_score, best_breakdown = scored[0]

        alternatives: List[Dict[str, Any]] = [
            {"agent_id": a.agent_id, "score": round(s, 6), "name": a.name}
            for a, s, _ in scored[1:4]
        ]

        elapsed_ms = (time.monotonic() - start) * 1000
        result = AssignmentResult(
            ticket_id=ticket.ticket_id,
            assigned_to=best_agent.agent_id,
            strategy="score_based",
            score=best_score,
            score_breakdown=best_breakdown,
            alternatives=alternatives,
            reason=f"Best score {best_score:.4f} for {best_agent.name}",
            latency_ms=elapsed_ms,
        )
        return result

    async def batch_assign(
        self,
        tickets: List[TicketContext],
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> List[AssignmentResult]:
        results: List[AssignmentResult] = []
        for ticket in tickets:
            result = await self.assign(ticket, agents, **kwargs)
            results.append(result)
        return results

    def clear_cache(self) -> None:
        """Drop all cached scores."""
        self._score_cache.clear()


# ---------------------------------------------------------------------------
# Hybrid Assigner
# ---------------------------------------------------------------------------

class HybridAssigner(BaseAssigner):
    """Score-based first; falls back to rule-based when the best score
    drops below a configurable threshold.
    """

    def __init__(
        self,
        redis_client: Any = None,
        min_score_threshold: float = 0.30,
    ) -> None:
        self.score_assigner = ScoreBasedAssigner(redis_client=redis_client)
        self.rule_assigner = RuleBasedAssigner(redis_client=redis_client)
        self.min_score_threshold = min_score_threshold
        self._fallback_count: int = 0
        self._direct_count: int = 0

    async def assign(
        self,
        ticket: TicketContext,
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> AssignmentResult:
        score_result = await self.score_assigner.assign(ticket, agents, **kwargs)

        if (
            score_result.score >= self.min_score_threshold
            and not score_result.is_unassigned
        ):
            score_result.strategy = "hybrid"
            score_result.reason = (
                f"Hybrid score-based (score={score_result.score:.4f} ≥ "
                f"threshold={self.min_score_threshold:.2f})"
            )
            self._direct_count += 1
            return score_result

        # Fallback to rule-based
        rule_result = await self.rule_assigner.assign(ticket, agents, **kwargs)
        rule_result.strategy = "hybrid"
        rule_result.reason = (
            f"Score {score_result.score:.4f} below threshold "
            f"{self.min_score_threshold:.2f}, fell back to rule-based: "
            f"{rule_result.reason}"
        )
        self._fallback_count += 1
        return rule_result

    async def batch_assign(
        self,
        tickets: List[TicketContext],
        agents: List[AgentProfile],
        **kwargs: Any,
    ) -> List[AssignmentResult]:
        results: List[AssignmentResult] = []
        for ticket in tickets:
            result = await self.assign(ticket, agents, **kwargs)
            results.append(result)
        return results

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "direct_score_assignments": self._direct_count,
            "rule_fallback_assignments": self._fallback_count,
        }


# ---------------------------------------------------------------------------
# Capacity Manager
# ---------------------------------------------------------------------------

class CapacityManager:
    """Tracks real-time agent capacity and enforces limits.

    Used by the ``AssignmentEngine`` to atomically increment / decrement
    agent load and to expose dashboard-ready capacity snapshots.
    """

    def __init__(self, redis_client: Any = None,
                 ttl_seconds: int = 300) -> None:
        self.redis = redis_client
        self.ttl = ttl_seconds
        self._load: Dict[str, int] = {}
        self._lock_store: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, agent_id: str) -> asyncio.Lock:
        if agent_id not in self._lock_store:
            self._lock_store[agent_id] = asyncio.Lock()
        return self._lock_store[agent_id]

    async def acquire_slot(self, agent_id: str, max_concurrent: int) -> bool:
        """Atomically increment load if capacity allows.  Returns True on success."""
        async with self._get_lock(agent_id):
            current = self._load.get(agent_id, 0)
            if current >= max_concurrent:
                return False
            self._load[agent_id] = current + 1
            if self.redis:
                try:
                    await self.redis.set(
                        f"capacity:{agent_id}", self._load[agent_id], ex=self.ttl
                    )
                except Exception:
                    logger.warning(
                        "Redis SET failed for capacity:%s", agent_id)
            return True

    async def release_slot(self, agent_id: str) -> None:
        """Atomically decrement load (floor = 0)."""
        async with self._get_lock(agent_id):
            current = self._load.get(agent_id, 0)
            self._load[agent_id] = max(0, current - 1)
            if self.redis:
                try:
                    await self.redis.set(
                        f"capacity:{agent_id}", self._load[agent_id], ex=self.ttl
                    )
                except Exception:
                    logger.warning(
                        "Redis SET failed for capacity:%s", agent_id)

    def get_load(self, agent_id: str) -> int:
        return self._load.get(agent_id, 0)

    def snapshot(self, agents: List[AgentProfile]) -> List[Dict[str, Any]]:
        """Return capacity info for every agent."""
        out: List[Dict[str, Any]] = []
        for agent in agents:
            current = self._load.get(agent.agent_id, agent.current_load)
            out.append({
                "agent_id": agent.agent_id,
                "name": agent.name,
                "current_load": current,
                "max_concurrent": agent.max_concurrent,
                "available": max(0, agent.max_concurrent - current),
                "utilization": round(current / max(1, agent.max_concurrent), 4),
            })
        return out

    def reset(self) -> None:
        self._load.clear()


# ---------------------------------------------------------------------------
# Assignment Event Bus (lightweight in-process pub/sub)
# ---------------------------------------------------------------------------

class AssignmentEvent:
    """Immutable record of an assignment event."""

    __slots__ = ("event_id", "event_type", "payload", "timestamp")

    def __init__(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        self.event_id = uuid.uuid4().hex[:12]
        self.event_type = event_type
        self.payload = payload
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class AssignmentEventBus:
    """Synchronous in-process pub/sub for assignment lifecycle events.

    Subscribers are plain ``callable`` that receive an ``AssignmentEvent``.
    All handlers are invoked in order; errors in one handler do not prevent
    others from running.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._subscribers: Dict[str, List[Any]] = {}
        self._history: List[AssignmentEvent] = []
        self._max_history = max_history

    def subscribe(self, event_type: str, handler: Any) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Any) -> None:
        handlers = self._subscribers.get(event_type, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    def publish(self, event: AssignmentEvent) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Event handler error for %s",
                    event.event_type)

    def get_history(
        self, event_type: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    def clear_history(self) -> None:
        self._history.clear()


# ---------------------------------------------------------------------------
# SLA helpers
# ---------------------------------------------------------------------------

class SLAHelper:
    """Utility for computing SLA deadlines and checking compliance."""

    # Target first-response SLA in seconds per priority / tier.
    SLA_TABLE: Dict[str, Dict[str, int]] = {
        "critical": {"standard": 900, "premium": 600, "enterprise": 300},
        "high": {"standard": 1800, "premium": 1200, "enterprise": 600},
        "medium": {"standard": 3600, "premium": 2700, "enterprise": 1800},
        "low": {"standard": 86400, "premium": 43200, "enterprise": 21600},
    }

    @classmethod
    def response_target_seconds(cls, priority: str, tier: str) -> int:
        return cls.SLA_TABLE.get(
            priority.lower(),
            cls.SLA_TABLE["medium"]).get(
            tier.lower(),
            3600)

    @classmethod
    def deadline_iso(
            cls,
            priority: str,
            tier: str,
            base: Optional[datetime] = None) -> str:
        if base is None:
            base = datetime.now(timezone.utc)
        target = cls.response_target_seconds(priority, tier)
        return (
            base
            + __import__("datetime").timedelta(
                seconds=target)).isoformat()

    @classmethod
    def is_within_sla(
        cls,
        assigned_at: str,
        responded_at: str,
        priority: str,
        tier: str,
    ) -> bool:
        try:
            a_dt = datetime.fromisoformat(assigned_at)
            r_dt = datetime.fromisoformat(responded_at)
            delta = (r_dt - a_dt).total_seconds()
            return delta <= cls.response_target_seconds(priority, tier)
        except (ValueError, TypeError):
            return False


# ---------------------------------------------------------------------------
# Utility: Deterministic hash-based jitter
# ---------------------------------------------------------------------------

def deterministic_jitter(
        ticket_id: str,
        agent_id: str,
        max_val: float = 0.05) -> float:
    """Reproducible jitter so the same ticket+agent always gets the same noise."""
    h = hashlib.md5(f"{ticket_id}:{agent_id}".encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) * max_val


# ---------------------------------------------------------------------------
# Assignment Engine (top-level orchestrator)
# ---------------------------------------------------------------------------

class AssignmentEngine:
    """Main engine with caching, capacity management, event bus, and metrics.

    Usage::

        engine = AssignmentEngine()
        result = await engine.assign(ticket, agents, strategy="hybrid")
    """

    def __init__(
        self,
        redis_client: Any = None,
        variant: str = "parwa",
        event_bus: Optional[AssignmentEventBus] = None,
    ) -> None:
        self.redis = redis_client
        self.variant = variant
        self._assigners: Dict[str, BaseAssigner] = {
            "score_based": ScoreBasedAssigner(redis_client),
            "rule_based": RuleBasedAssigner(redis_client),
            "hybrid": HybridAssigner(redis_client),
        }
        self._capacity = CapacityManager(redis_client)
        self._event_bus = event_bus or AssignmentEventBus()
        self._metrics: Dict[str, Any] = {
            "total_assigned": 0,
            "total_unassigned": 0,
            "strategy_counts": {},
            "total_latency_ms": 0.0,
            "errors": 0,
        }
        self._recent_results: List[AssignmentResult] = []

    # -- core API --

    async def assign(
        self,
        ticket: TicketContext,
        agents: List[AgentProfile],
        strategy: str = "hybrid",
        **kwargs: Any,
    ) -> AssignmentResult:
        """Assign a single ticket and emit lifecycle events."""
        assigner = self._assigners.get(strategy, self._assigners["hybrid"])
        try:
            result = await assigner.assign(ticket, agents, **kwargs)
        except Exception as exc:
            logger.exception(
                "Assignment error for ticket %s",
                ticket.ticket_id)
            self._metrics["errors"] += 1
            result = AssignmentResult(
                ticket_id=ticket.ticket_id,
                assigned_to="unassigned",
                strategy=strategy,
                reason=f"Error: {exc}",
            )

        # Update metrics
        if result.is_unassigned:
            self._metrics["total_unassigned"] += 1
        else:
            self._metrics["total_assigned"] += 1
            # Acquire capacity
            assigned_agent = next(
                (a for a in agents if a.agent_id == result.assigned_to), None
            )
            if assigned_agent is not None:
                await self._capacity.acquire_slot(
                    assigned_agent.agent_id, assigned_agent.max_concurrent
                )

        self._metrics["strategy_counts"][result.strategy] = (
            self._metrics["strategy_counts"].get(result.strategy, 0) + 1
        )
        self._metrics["total_latency_ms"] += result.latency_ms

        # Stash recent results
        self._recent_results.append(result)
        if len(self._recent_results) > 200:
            self._recent_results = self._recent_results[-200:]

        # Publish event
        self._event_bus.publish(
            AssignmentEvent(
                event_type="ticket.assigned" if not result.is_unassigned else "ticket.unassigned",
                payload=result.to_dict(),
            ))

        return result

    async def batch_assign(
        self,
        tickets: List[TicketContext],
        agents: List[AgentProfile],
        strategy: str = "hybrid",
        **kwargs: Any,
    ) -> List[AssignmentResult]:
        """Assign multiple tickets sequentially."""
        assigner = self._assigners.get(strategy, self._assigners["hybrid"])
        return await assigner.batch_assign(tickets, agents, **kwargs)

    async def release_agent(self, agent_id: str) -> None:
        """Release a capacity slot for *agent_id* (call when ticket is resolved)."""
        await self._capacity.release_slot(agent_id)

    # -- introspection --

    def get_metrics(self) -> Dict[str, Any]:
        m = self._metrics.copy()
        total = m["total_assigned"] + m["total_unassigned"]
        m["avg_latency_ms"] = (
            round(m["total_latency_ms"] / max(1, total), 2)
        )
        return m

    def get_recent_results(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._recent_results[-limit:]]

    def get_capacity_snapshot(
            self, agents: List[AgentProfile]) -> List[Dict[str, Any]]:
        return self._capacity.snapshot(agents)

    def get_event_history(
            self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self._event_bus.get_history(event_type=event_type, limit=limit)

    def subscribe(self, event_type: str, handler: Any) -> None:
        self._event_bus.subscribe(event_type, handler)

    def reset(self) -> None:
        """Reset all engine state (useful in tests)."""
        self._metrics = {
            "total_assigned": 0,
            "total_unassigned": 0,
            "strategy_counts": {},
            "total_latency_ms": 0.0,
            "errors": 0,
        }
        self._recent_results.clear()
        self._capacity.reset()
        self._event_bus.clear_history()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_engine(
    strategy: str = "hybrid",
    redis_client: Any = None,
    variant: str = "parwa",
) -> AssignmentEngine:
    """Convenience factory."""
    return AssignmentEngine(redis_client=redis_client, variant=variant)


def create_agents(n: int, base_id: str = "agent") -> List[AgentProfile]:
    """Generate *n* dummy agents (handy for demos / tests)."""
    specialties_pool = [
        "billing", "technical", "general", "onboarding",
        "security", "integrations", "api", "premium_support",
    ]
    agents: List[AgentProfile] = []
    for i in range(1, n + 1):
        specs = random.sample(specialties_pool, k=min(3, random.randint(1, 3)))
        agents.append(AgentProfile(
            agent_id=f"{base_id}_{i:03d}",
            name=f"Agent {i}",
            email=f"agent{i}@parwa.io",
            specialties=specs,
            is_online=random.random() > 0.1,
            max_concurrent=random.choice([3, 5, 8, 10]),
            current_load=random.randint(0, 3),
            accuracy_score=round(random.uniform(0.80, 1.00), 2),
            avg_response_time=round(random.uniform(120, 600), 1),
            seniority_years=round(random.uniform(0.0, 10.0), 1),
            languages=random.sample(["en", "es", "fr", "de", "pt"], k=random.randint(1, 3)),
        ))
    return agents


def create_tickets(n: int, base_id: str = "tkt") -> List[TicketContext]:
    """Generate *n* dummy tickets."""
    categories = ["billing", "technical", "general", "onboarding", "security"]
    priorities = ["critical", "high", "medium", "low"]
    tiers = ["standard", "premium", "enterprise"]
    tickets: List[TicketContext] = []
    for i in range(1, n + 1):
        cat = random.choice(categories)
        tickets.append(TicketContext(
            ticket_id=f"{base_id}_{i:04d}",
            subject=f"Issue with {cat} — ticket #{i}",
            description=f"Detailed description for {cat} issue #{i}.",
            category=cat,
            priority=random.choice(priorities),
            customer_tier=random.choice(tiers),
            tags=[cat, random.choice(["urgent", "feature_request", "bug"])],
            language=random.choice(["en", "es", "fr"]),
            channel=random.choice(["email", "chat", "phone", "portal"]),
            estimated_complexity=round(random.uniform(0.1, 1.0), 2),
        ))
    return tickets
