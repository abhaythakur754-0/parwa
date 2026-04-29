"""
PARWA AI Assignment Engine (F-050) — AI-Powered Ticket Assignment

Score-based multi-factor assignment:
  specialty (40) + workload (30) + historical accuracy (20) + jitter (10) = 100

Variant differentiation:
  mini_parwa  — specialty + workload only (simpler), max 5 agents
  parwa       — full 4-factor scoring, max 10 agents
  high_parwa  — full scoring + learning from history + reassignment optimization

GAP-027 FIX: Deterministic jitter via SHA-256 hash of ticket_id:agent_id
  so the same ticket always receives the same score per agent.

BC-001: All queries are tenant-isolated via company_id.
BC-008: Graceful degradation — falls back to rule-based or round-robin.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════


class VariantType(str, Enum):
    """PARWA variant tiers controlling assignment complexity."""
    MINI_PARWA = "mini_parwa"
    PARWA = "parwa"
    PARWA_HIGH = "high_parwa"


class AssignmentMethod(str, Enum):
    """How a ticket was assigned."""
    AI_SCORED = "ai_scored"
    RULE_BASED = "rule_based"
    FALLBACK = "fallback"
    MANUAL = "manual"


# Score weights per factor (max total = 100)
SPECIALTY_MAX = 40.0
WORKLOAD_MAX = 30.0
ACCURACY_MAX = 20.0
JITTER_MAX = 10.0

# Variant-specific max agent pool sizes
VARIANT_MAX_AGENTS: Dict[str, int] = {
    "mini_parwa": 5,
    "parwa": 10,
    "high_parwa": 10,
}

# Redis cache TTL for agent workloads (seconds)
WORKLOAD_CACHE_TTL = 300

# Sentiment thresholds
NEGATIVE_SENTIMENT_THRESHOLD = 0.3
VERY_NEGATIVE_SENTIMENT_THRESHOLD = 0.15


# ── Intent → Skill Mapping ────────────────────────────────────────


INTENT_SKILL_MAP: Dict[str, List[str]] = {
    "refund": ["refunds", "billing", "payment"],
    "technical": ["technical", "engineering", "debugging", "troubleshooting"],
    "billing": ["billing", "payments", "invoices", "pricing"],
    "complaint": ["customer_success", "escalation", "conflict_resolution"],
    "feature_request": ["product", "development", "feedback"],
    "cancellation": ["retention", "customer_success", "billing"],
    "shipping": ["logistics", "fulfillment", "orders"],
    "inquiry": ["general", "support"],
    "escalation": ["senior", "escalation", "management"],
    "account": ["account_management", "security"],
    "feedback": ["product", "customer_success"],
    "general": ["general", "support"],
}

# Priority-specific multipliers for each scoring factor
PRIORITY_WEIGHTS: Dict[str, Dict[str, float]] = {
    "low": {
        "specialty_mult": 0.8,
        "workload_mult": 1.0,
        "accuracy_mult": 0.8,
    },
    "medium": {
        "specialty_mult": 1.0,
        "workload_mult": 1.0,
        "accuracy_mult": 1.0,
    },
    "high": {
        "specialty_mult": 1.2,
        "workload_mult": 0.8,
        "accuracy_mult": 1.2,
    },
    "critical": {
        "specialty_mult": 1.5,
        "workload_mult": 0.6,
        "accuracy_mult": 1.5,
    },
}

# Channel-specific skill adjustments
CHANNEL_SKILL_BONUS: Dict[str, List[str]] = {
    "phone": ["verbal_communication", "de_escalation"],
    "chat": ["fast_typing", "multi_tasking"],
    "email": ["written_communication", "documentation"],
    "social": ["brand_voice", "public_relations"],
}

# Customer tier priority boost
CUSTOMER_TIER_BOOST: Dict[str, float] = {
    "free": 0.0,
    "basic": 0.0,
    "pro": 2.0,
    "enterprise": 5.0,
}


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class TicketAssignmentRequest:
    """Input for AI ticket assignment.

    Carries all signals needed for multi-factor scoring.
    """
    ticket_id: str
    company_id: str
    variant_type: str  # mini_parwa, parwa, high_parwa
    intent_type: str  # refund, technical, billing, complaint, etc.
    priority: str  # low, medium, high, critical
    sentiment_score: float  # 0.0 – 1.0
    customer_tier: str  # free, basic, pro, enterprise
    customer_id: Optional[str] = None
    required_skills: Optional[List[str]] = None
    language: str = "en"
    channel: str = "email"  # email, chat, phone, social


@dataclass
class TicketAssignmentResult:
    """Output of AI ticket assignment."""
    ticket_id: str
    assigned_agent_id: str
    assigned_agent_name: str
    assignment_method: str  # ai_scored, rule_based, fallback, manual
    total_score: float
    score_breakdown: Dict[str, float]  # specialty, workload, accuracy, jitter
    confidence: float  # 0.0 – 1.0
    alternatives: List[Dict[str, Any]]  # next-best agents
    assignment_time_ms: float
    reason: str
    assigned_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


@dataclass
class AgentScore:
    """Detailed per-agent scoring breakdown."""
    agent_id: str
    agent_name: str
    specialty_score: float  # 0–40
    workload_score: float  # 0–30
    accuracy_score: float  # 0–20
    jitter_score: float  # 0–10
    total_score: float  # 0–100
    is_available: bool
    skills_match: List[str]
    historical_accuracy: float
    current_workload: int
    max_workload: int


@dataclass
class AgentWorkload:
    """Current workload snapshot for one agent."""
    agent_id: str
    agent_name: str
    current_tickets: int
    max_capacity: int
    utilization_pct: float
    is_overloaded: bool
    skills: List[str]
    specialty: str


@dataclass
class AssignmentEvent:
    """Historical assignment event for a ticket."""
    event_id: str
    ticket_id: str
    company_id: str
    agent_id: Optional[str]
    agent_name: Optional[str]
    method: str
    score: Optional[float]
    reason: str
    assigned_at: str


@dataclass
class TrainingResult:
    """Result of model training on historical data."""
    company_id: str
    samples_processed: int
    accuracy_before: float
    accuracy_after: float
    improvement_pct: float
    features_updated: List[str]
    trained_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    status: str = "success"


@dataclass
class _AgentProfile:
    """Internal agent profile used for scoring (not exposed)."""
    agent_id: str
    name: str
    skills: List[str]
    specialty: str
    max_workload: int
    current_workload: int
    resolution_rate: float  # 0.0 – 1.0
    avg_csat: float  # 1.0 – 5.0
    avg_response_time: float  # minutes
    is_active: bool = True
    languages: List[str] = field(default_factory=lambda: ["en"])
    channels: List[str] = field(
        default_factory=lambda: [
            "email", "chat", "phone", "social"])


# ══════════════════════════════════════════════════════════════════
# MOCK AGENTS (Development)
# ══════════════════════════════════════════════════════════════════


DEFAULT_AGENTS: List[Dict[str,
                          Any]] = [{"agent_id": "agent_001",
                                    "name": "Sarah Chen",
                                    "skills": ["technical",
                                               "debugging",
                                               "engineering",
                                               "troubleshooting"],
                                    "specialty": "technical",
                                    "max_workload": 15,
                                    "resolution_rate": 0.92,
                                    "avg_csat": 4.5,
                                    "avg_response_time": 5.2,
                                    },
                                   {"agent_id": "agent_002",
                                    "name": "Mike Johnson",
                                    "skills": ["billing",
                                               "payments",
                                               "invoices",
                                               "pricing",
                                               "refunds"],
                                    "specialty": "billing",
                                    "max_workload": 20,
                                    "resolution_rate": 0.88,
                                    "avg_csat": 4.3,
                                    "avg_response_time": 8.1,
                                    },
                                   {"agent_id": "agent_003",
                                    "name": "Elena Rodriguez",
                                    "skills": ["customer_success",
                                               "escalation",
                                               "conflict_resolution",
                                               "retention"],
                                    "specialty": "customer_success",
                                    "max_workload": 12,
                                    "resolution_rate": 0.95,
                                    "avg_csat": 4.8,
                                    "avg_response_time": 4.5,
                                    },
                                   {"agent_id": "agent_004",
                                    "name": "James Park",
                                    "skills": ["product",
                                               "development",
                                               "feedback",
                                               "feature_request"],
                                    "specialty": "product",
                                    "max_workload": 10,
                                    "resolution_rate": 0.85,
                                    "avg_csat": 4.1,
                                    "avg_response_time": 12.3,
                                    },
                                   {"agent_id": "agent_005",
                                    "name": "Aisha Patel",
                                    "skills": ["logistics",
                                               "fulfillment",
                                               "orders",
                                               "shipping"],
                                    "specialty": "shipping",
                                    "max_workload": 18,
                                    "resolution_rate": 0.90,
                                    "avg_csat": 4.4,
                                    "avg_response_time": 6.7,
                                    },
                                   {"agent_id": "agent_006",
                                    "name": "David Kim",
                                    "skills": ["general",
                                               "support",
                                               "inquiry",
                                               "billing"],
                                    "specialty": "general",
                                    "max_workload": 25,
                                    "resolution_rate": 0.82,
                                    "avg_csat": 3.9,
                                    "avg_response_time": 10.5,
                                    },
                                   {"agent_id": "agent_007",
                                    "name": "Maria Santos",
                                    "skills": ["senior",
                                               "escalation",
                                               "management",
                                               "customer_success"],
                                    "specialty": "escalation",
                                    "max_workload": 8,
                                    "resolution_rate": 0.97,
                                    "avg_csat": 4.9,
                                    "avg_response_time": 3.8,
                                    },
                                   {"agent_id": "agent_008",
                                    "name": "Tom Williams",
                                    "skills": ["account_management",
                                               "security",
                                               "general",
                                               "billing"],
                                    "specialty": "account",
                                    "max_workload": 14,
                                    "resolution_rate": 0.87,
                                    "avg_csat": 4.2,
                                    "avg_response_time": 7.9,
                                    },
                                   {"agent_id": "agent_009",
                                    "name": "Yuki Tanaka",
                                    "skills": ["technical",
                                               "engineering",
                                               "debugging",
                                               "product"],
                                    "specialty": "technical",
                                    "max_workload": 16,
                                    "resolution_rate": 0.91,
                                    "avg_csat": 4.6,
                                    "avg_response_time": 5.8,
                                    "languages": ["en",
                                                  "ja"],
                                    },
                                   {"agent_id": "agent_010",
                                    "name": "Carlos Mendez",
                                    "skills": ["retention",
                                               "customer_success",
                                               "billing",
                                               "conflict_resolution"],
                                    "specialty": "cancellation",
                                    "max_workload": 11,
                                    "resolution_rate": 0.93,
                                    "avg_csat": 4.7,
                                    "avg_response_time": 6.2,
                                    "languages": ["en",
                                                  "es"],
                                    },
                                   ]


def _build_agent_profiles(
    agents_data: Optional[List[Dict[str, Any]]] = None,
) -> List[_AgentProfile]:
    """Convert raw agent dicts to _AgentProfile objects."""
    data = agents_data or DEFAULT_AGENTS
    profiles: List[_AgentProfile] = []
    for a in data:
        profiles.append(_AgentProfile(
            agent_id=a["agent_id"],
            name=a["name"],
            skills=a.get("skills", []),
            specialty=a.get("specialty", "general"),
            max_workload=a.get("max_workload", 15),
            current_workload=a.get("current_workload", 0),
            resolution_rate=a.get("resolution_rate", 0.80),
            avg_csat=a.get("avg_csat", 4.0),
            avg_response_time=a.get("avg_response_time", 10.0),
            is_active=a.get("is_active", True),
            languages=a.get("languages", ["en"]),
            channels=a.get("channels", ["email", "chat", "phone", "social"]),
        ))
    return profiles


# ══════════════════════════════════════════════════════════════════
# AI ASSIGNMENT ENGINE
# ══════════════════════════════════════════════════════════════════


class AIAssignmentEngine:
    """AI-powered ticket assignment with multi-factor scoring.

    Orchestrates score-based assignment using:
      specialty  (0–40)  — skill / intent match
      workload   (0–30)  — capacity utilisation
      accuracy   (0–20)  — historical resolution quality
      jitter     (0–10)  — deterministic tie-breaking (GAP-027)

    Variant gating controls scoring depth:
      mini_parwa  — specialty + workload only
      parwa       — full 4-factor scoring
      high_parwa  — full scoring + history learning

    BC-001: company_id isolates all data.
    BC-008: Falls back to rule-based or round-robin on failure.
    BC-012: All timestamps are UTC.
    """

    def __init__(
        self,
        db: Optional[Any] = None,
        redis_client: Optional[Any] = None,
        assignment_service: Optional[Any] = None,
    ) -> None:
        self.db = db
        self.redis = redis_client
        self._assignment_service = assignment_service
        self._agent_profiles: Optional[List[_AgentProfile]] = None

        # In-memory history store (high_parwa learning).  In production
        # this would be persisted in the database or a vector store.
        self._assignment_history: Dict[str, List[AssignmentEvent]] = {}

        # Trained model weights (high_parwa).  Start with defaults.
        self._model_weights: Dict[str, Dict[str, float]] = {
            "specialty": {"weight": 1.0, "bias": 0.0},
            "workload": {"weight": 1.0, "bias": 0.0},
            "accuracy": {"weight": 1.0, "bias": 0.0},
        }

        logger.info(
            "AIAssignmentEngine initialized (db=%s, redis=%s)",
            db is not None, redis_client is not None,
        )

    # ── Lazy-loaded dependencies ─────────────────────────────────

    @property
    def assignment_service(self) -> Any:
        """Lazy-load the AssignmentService (import inside property to avoid circular imports)."""
        if self._assignment_service is None and self.db is not None:
            try:
                from app.services.assignment_service import AssignmentService
                self._assignment_service = AssignmentService(
                    self.db, company_id="__placeholder__")
            except Exception as exc:
                logger.warning(
                    "Could not lazy-load AssignmentService: %s", exc)
        return self._assignment_service

    # ── PUBLIC API ───────────────────────────────────────────────

    async def assign_ticket(
        self,
        request: TicketAssignmentRequest,
    ) -> TicketAssignmentResult:
        """Assign a single ticket to the best agent.

        Args:
            request: Full ticket context with intent, priority, sentiment, etc.

        Returns:
            TicketAssignmentResult with agent, score breakdown, and confidence.
        """
        start_ms = time.monotonic() * 1000

        try:
            result = await self._assign_safe(request)
        except Exception:
            # BC-008: graceful degradation — fall back to round-robin
            logger.exception(
                "AI assignment failed for ticket=%s company=%s, falling back to round-robin",
                request.ticket_id,
                request.company_id,
            )
            result = await self._fallback_assign(request)

        elapsed = time.monotonic() * 1000 - start_ms
        result.assignment_time_ms = round(elapsed, 2)

        # Persist assignment event in memory
        await self._record_assignment_event(request, result)

        logger.info(
            "Ticket %s assigned to %s (method=%s, score=%.1f, time=%.1fms)",
            request.ticket_id, result.assigned_agent_id,
            result.assignment_method, result.total_score, elapsed,
        )
        return result

    async def get_assignment_scores(
        self,
        request: TicketAssignmentRequest,
    ) -> List[AgentScore]:
        """Score all available agents for a ticket without assigning.

        Useful for preview / manual override workflows.

        Args:
            request: Ticket assignment context.

        Returns:
            List of AgentScore objects sorted by total_score descending.
        """
        try:
            agents = await self._get_available_agents(request.company_id)
            scores = await self._calculate_scores(request, agents)
            return sorted(scores, key=lambda s: s.total_score, reverse=True)
        except Exception:
            logger.exception(
                "Score calculation failed for ticket=%s company=%s",
                request.ticket_id, request.company_id,
            )
            return []

    async def batch_assign(
        self,
        requests: List[TicketAssignmentRequest],
    ) -> List[TicketAssignmentResult]:
        """Assign multiple tickets concurrently.

        Args:
            requests: List of ticket assignment requests.

        Returns:
            List of results in the same order as input requests.
        """
        if not requests:
            return []

        # Execute with concurrency cap to avoid overloading Redis / DB
        semaphore = asyncio.Semaphore(10)

        async def _guarded(
                req: TicketAssignmentRequest) -> TicketAssignmentResult:
            async with semaphore:
                return await self.assign_ticket(req)

        results = await asyncio.gather(
            *[_guarded(r) for r in requests],
            return_exceptions=True,
        )

        output: List[TicketAssignmentResult] = []
        for idx, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(
                    "Batch assign[%d] failed for ticket=%s: %s",
                    idx, requests[idx].ticket_id, res,
                )
                # BC-008: produce a fallback result
                output.append(await self._fallback_assign(requests[idx]))
            else:
                output.append(res)

        logger.info(
            "Batch assignment complete: %d/%d succeeded",
            sum(1 for r in output if r.assignment_method != "fallback"),
            len(output),
        )
        return output

    async def reassign_ticket(
        self,
        ticket_id: str,
        company_id: str,
        reason: str,
    ) -> TicketAssignmentResult:
        """Reassign an existing ticket to a different agent.

        Picks the next-best agent (excluding the current one).

        Args:
            ticket_id: Ticket to reassign.
            company_id: Tenant identifier.
            reason: Why reassignment is needed.

        Returns:
            New TicketAssignmentResult.
        """
        # Look up the current assignment to exclude that agent
        previous_agent_id = await self._get_current_assignee(ticket_id, company_id)

        # Build a synthetic request (we don't have the full ticket context,
        # so we use conservative defaults).
        request = TicketAssignmentRequest(
            ticket_id=ticket_id,
            company_id=company_id,
            variant_type="parwa",
            intent_type="general",
            priority="medium",
            sentiment_score=0.5,
            customer_tier="basic",
        )

        agents = await self._get_available_agents(company_id)

        # Exclude the current assignee
        if previous_agent_id:
            agents = [a for a in agents if a.agent_id != previous_agent_id]

        if not agents:
            logger.warning(
                "No alternative agents available for reassignment of ticket=%s",
                ticket_id,
            )
            return TicketAssignmentResult(
                ticket_id=ticket_id,
                assigned_agent_id=previous_agent_id or "",
                assigned_agent_name="",
                assignment_method="fallback",
                total_score=0.0,
                score_breakdown={},
                confidence=0.0,
                alternatives=[],
                assignment_time_ms=0.0,
                reason=f"Reassignment failed: no alternative agents. Original reason: {reason}",
            )

        scores = await self._calculate_scores(request, agents)

        # high_parwa: incorporate historical reassignment patterns
        variant = await self._detect_variant(company_id)
        if variant == VariantType.PARWA_HIGH.value:
            scores = await self._apply_reassignment_optimization(scores, ticket_id)

        best = scores[0] if scores else None
        if best is None:
            return TicketAssignmentResult(
                ticket_id=ticket_id,
                assigned_agent_id=previous_agent_id or "",
                assigned_agent_name="",
                assignment_method="fallback",
                total_score=0.0,
                score_breakdown={},
                confidence=0.0,
                alternatives=[],
                assignment_time_ms=0.0,
                reason=f"Reassignment fallback. Original reason: {reason}",
            )

        alternatives = [
            {
                "agent_id": s.agent_id,
                "agent_name": s.agent_name,
                "total_score": s.total_score,
            }
            for s in scores[1:4]
        ]

        confidence = self._compute_confidence(scores)

        result = TicketAssignmentResult(
            ticket_id=ticket_id,
            assigned_agent_id=best.agent_id,
            assigned_agent_name=best.agent_name,
            assignment_method="ai_scored",
            total_score=round(best.total_score, 2),
            score_breakdown={
                "specialty": round(best.specialty_score, 2),
                "workload": round(best.workload_score, 2),
                "accuracy": round(best.accuracy_score, 2),
                "jitter": round(best.jitter_score, 2),
            },
            confidence=round(confidence, 4),
            alternatives=alternatives,
            assignment_time_ms=0.0,
            reason=f"AI reassignment: {reason}",
        )

        await self._record_assignment_event(
            TicketAssignmentRequest(
                ticket_id=ticket_id,
                company_id=company_id,
                variant_type=variant,
                intent_type=request.intent_type,
                priority=request.priority,
                sentiment_score=request.sentiment_score,
                customer_tier=request.customer_tier,
            ),
            result,
        )

        logger.info(
            "Ticket %s reassigned from %s to %s: %s",
            ticket_id, previous_agent_id, best.agent_id, reason,
        )
        return result

    async def get_agent_workload(
        self,
        company_id: str,
    ) -> Dict[str, AgentWorkload]:
        """Get current workload for all agents in a company.

        Uses Redis cache with TTL=300s for performance.

        Args:
            company_id: Tenant identifier.

        Returns:
            Dict mapping agent_id → AgentWorkload.
        """
        cache_key = f"workload:{company_id}"

        # Try cache first
        if self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached) if isinstance(
                        cached, str) else cached
                    return {
                        aid: AgentWorkload(
                            **info) for aid,
                        info in data.items()}
            except Exception:
                logger.warning(
                    "Redis cache read failed for workload key=%s",
                    cache_key)

        # Compute from profiles
        agents = await self._get_available_agents(company_id)
        workloads: Dict[str, AgentWorkload] = {}

        for agent in agents:
            util = (
                agent.current_workload / agent.max_workload
                if agent.max_workload > 0
                else 0.0
            )
            workloads[agent.agent_id] = AgentWorkload(
                agent_id=agent.agent_id,
                agent_name=agent.name,
                current_tickets=agent.current_workload,
                max_capacity=agent.max_workload,
                utilization_pct=round(util * 100, 1),
                is_overloaded=agent.current_workload >= agent.max_workload,
                skills=agent.skills,
                specialty=agent.specialty,
            )

        # Write to cache
        if self.redis is not None:
            try:
                serialisable = {
                    aid: {
                        "agent_id": w.agent_id,
                        "agent_name": w.agent_name,
                        "current_tickets": w.current_tickets,
                        "max_capacity": w.max_capacity,
                        "utilization_pct": w.utilization_pct,
                        "is_overloaded": w.is_overloaded,
                        "skills": w.skills,
                        "specialty": w.specialty,
                    }
                    for aid, w in workloads.items()
                }
                await self.redis.set(
                    cache_key,
                    json.dumps(serialisable),
                    ex=WORKLOAD_CACHE_TTL,
                )
            except Exception:
                logger.warning(
                    "Redis cache write failed for workload key=%s",
                    cache_key)

        return workloads

    async def get_assignment_history(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[AssignmentEvent]:
        """Retrieve the assignment history for a ticket.

        Uses in-memory store for high_parwa; falls back to AssignmentService
        for DB-backed history.

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket whose history to fetch.

        Returns:
            List of AssignmentEvent objects, newest first.
        """
        key = f"{company_id}:{ticket_id}"

        # In-memory events
        mem_events = self._assignment_history.get(key, [])

        # DB events via AssignmentService
        db_events: List[AssignmentEvent] = []
        if self.assignment_service is not None and self.db is not None:
            try:
                self.assignment_service.company_id = company_id
                raw = self.assignment_service.get_assignment_history(ticket_id)
                for r in raw:
                    db_events.append(AssignmentEvent(
                        event_id=r.get("id", ""),
                        ticket_id=ticket_id,
                        company_id=company_id,
                        agent_id=r.get("assignee_id"),
                        agent_name=None,
                        method=r.get("assignee_type", "unknown"),
                        score=r.get("score"),
                        reason=r.get("reason", ""),
                        assigned_at=r.get("assigned_at", ""),
                    ))
            except Exception as exc:
                logger.warning("DB history fetch failed: %s", exc)

        # Merge and deduplicate by event_id
        seen_ids: set = set()
        merged: List[AssignmentEvent] = []
        for event in mem_events + db_events:
            if event.event_id and event.event_id not in seen_ids:
                seen_ids.add(event.event_id)
                merged.append(event)

        merged.sort(key=lambda e: e.assigned_at, reverse=True)
        return merged

    async def train_model(
        self,
        company_id: str,
        historical_data: List[Dict[str, Any]],
    ) -> TrainingResult:
        """Train / fine-tune the scoring model from historical outcomes.

        Analyses past assignments to learn per-company weight adjustments.
        Currently adjusts specialty, workload, and accuracy weights.

        Args:
            company_id: Tenant identifier.
            historical_data: List of past assignment records with outcomes.

        Returns:
            TrainingResult with before/after accuracy metrics.
        """
        if not historical_data:
            return TrainingResult(
                company_id=company_id,
                samples_processed=0,
                accuracy_before=0.0,
                accuracy_after=0.0,
                improvement_pct=0.0,
                features_updated=[],
                status="skipped_no_data",
            )

        samples = len(historical_data)
        logger.info(
            "Training model for company=%s with %d samples",
            company_id, samples,
        )

        # Baseline accuracy: simulated before-training performance
        accuracy_before = self._estimate_model_accuracy(historical_data)

        # Learn weight adjustments from historical outcomes
        weight_updates = self._learn_weights(historical_data)
        features_updated = list(weight_updates.keys())

        # Apply learned weights
        for factor, adjustment in weight_updates.items():
            if factor in self._model_weights:
                self._model_weights[factor]["weight"] = max(
                    0.1, min(2.0, self._model_weights[factor]["weight"] + adjustment),
                )
                self._model_weights[factor]["bias"] = max(-5.0, min(
                    5.0, self._model_weights[factor]["bias"] + adjustment * 0.5), )

        # Simulated after-training accuracy
        accuracy_after = self._estimate_model_accuracy(
            historical_data, trained=True)
        improvement = (
            ((accuracy_after - accuracy_before) / max(accuracy_before, 0.01)) * 100
            if accuracy_before > 0
            else 0.0
        )

        result = TrainingResult(
            company_id=company_id,
            samples_processed=samples,
            accuracy_before=round(accuracy_before, 4),
            accuracy_after=round(accuracy_after, 4),
            improvement_pct=round(improvement, 2),
            features_updated=features_updated,
            status="success",
        )

        logger.info(
            "Model training complete for company=%s: improvement=%.1f%%",
            company_id, improvement,
        )
        return result

    # ════════════════════════════════════════════════════════════════
    # SCORING ENGINE
    # ════════════════════════════════════════════════════════════════

    async def _calculate_scores(
        self,
        request: TicketAssignmentRequest,
        agents: List[_AgentProfile],
    ) -> List[AgentScore]:
        """Score every available agent for a ticket.

        Applies variant-specific scoring (mini_parwa skips accuracy + jitter).
        Applies priority multipliers and customer-tier boosts.
        """
        variant = request.variant_type.lower()
        priority = request.priority.lower()
        weights = PRIORITY_WEIGHTS.get(priority, PRIORITY_WEIGHTS["medium"])
        tier_boost = CUSTOMER_TIER_BOOST.get(request.customer_tier, 0.0)

        # high_parwa: apply trained model weight adjustments
        if variant == VariantType.PARWA_HIGH.value:
            weights = self._apply_trained_weights(weights)

        # Filter agents by variant max pool
        max_agents = VARIANT_MAX_AGENTS.get(variant, 10)

        scores: List[AgentScore] = []
        for agent in agents[:max_agents]:
            # ── 1. Specialty Score (0–40) ──
            specialty_raw = self._score_specialty(
                agent.skills, request.intent_type, request.required_skills,
            )
            specialty_score = min(
                specialty_raw * weights["specialty_mult"],
                SPECIALTY_MAX,
            )

            # ── 2. Workload Score (0–30) ──
            workload_raw = self._score_workload(
                agent.current_workload, agent.max_workload,
            )
            workload_score = min(
                workload_raw * weights["workload_mult"],
                WORKLOAD_MAX,
            )

            # ── 3. Accuracy Score (0–20) — skipped for mini_parwa ──
            if variant == VariantType.MINI_PARWA.value:
                accuracy_score = 0.0
            else:
                accuracy_raw = self._score_accuracy(
                    agent.resolution_rate, agent.avg_csat, agent.avg_response_time, )
                accuracy_score = min(
                    accuracy_raw * weights["accuracy_mult"],
                    ACCURACY_MAX,
                )

            # ── 4. Jitter (0–10) — skipped for mini_parwa ──
            if variant == VariantType.MINI_PARWA.value:
                jitter_score = 0.0
            else:
                jitter_score = self._deterministic_jitter(
                    request.ticket_id, agent.agent_id,
                )

            # Language match bonus (high_parwa)
            language_bonus = 0.0
            if variant == VariantType.PARWA_HIGH.value:
                if request.language in agent.languages:
                    language_bonus = 1.5

            # Sentiment adjustment: negative sentiment → favour senior agents
            sentiment_adj = 0.0
            if request.sentiment_score < NEGATIVE_SENTIMENT_THRESHOLD:
                # Boost agents with high CSAT and escalation skills
                if "escalation" in agent.skills or agent.avg_csat >= 4.5:
                    sentiment_adj = 3.0

            # Channel bonus
            channel_bonus = self._channel_bonus(agent, request.channel)

            total = (
                specialty_score
                + workload_score
                + accuracy_score
                + jitter_score
                + tier_boost
                + language_bonus
                + sentiment_adj
                + channel_bonus
            )
            total = min(total, 100.0)

            # Determine matching skills
            intent_skills = INTENT_SKILL_MAP.get(request.intent_type, [])
            skills_match = list(set(agent.skills) & set(intent_skills))
            if request.required_skills:
                skills_match = list(
                    set(skills_match) | set(
                        agent.skills) & set(
                        request.required_skills))

            scores.append(AgentScore(
                agent_id=agent.agent_id,
                agent_name=agent.name,
                specialty_score=round(specialty_score, 2),
                workload_score=round(workload_score, 2),
                accuracy_score=round(accuracy_score, 2),
                jitter_score=round(jitter_score, 2),
                total_score=round(total, 2),
                is_available=agent.current_workload < agent.max_workload,
                skills_match=skills_match,
                historical_accuracy=round(agent.resolution_rate, 4),
                current_workload=agent.current_workload,
                max_workload=agent.max_workload,
            ))

        # Sort by total score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)
        return scores

    # ── Individual scoring factors ───────────────────────────────

    @staticmethod
    def _score_specialty(
        agent_skills: List[str],
        intent_type: str,
        required_skills: Optional[List[str]] = None,
    ) -> float:
        """Score how well an agent's skills match the ticket intent (0–40).

        Computes overlap between agent skills and the intent's ideal skill set.
        """
        if not intent_type:
            return 20.0  # neutral midpoint

        # Get ideal skills for this intent
        ideal_skills = set(
            INTENT_SKILL_MAP.get(
                intent_type, [
                    "general", "support"]))

        # Add any explicitly required skills
        if required_skills:
            ideal_skills.update(required_skills)

        agent_skill_set = set(agent_skills)

        if not ideal_skills:
            return 20.0

        # Exact match ratio
        matched = len(agent_skill_set & ideal_skills)
        total_ideal = len(ideal_skills)
        base_score = (matched / total_ideal) * SPECIALTY_MAX

        # Bonus for specialty alignment
        specialty_intents = {
            skill: intent
            for intent, skills in INTENT_SKILL_MAP.items()
            for skill in skills
        }
        for skill in agent_skills:
            mapped_intent = specialty_intents.get(skill)
            if mapped_intent == intent_type:
                base_score = min(base_score + 5.0, SPECIALTY_MAX)
                break

        return base_score

    @staticmethod
    def _score_workload(current: int, max_capacity: int) -> float:
        """Score based on agent's current workload utilisation (0–30).

        Lower utilisation → higher score (more available).
        Overloaded agents get a heavily penalised score.
        """
        if max_capacity <= 0:
            return 0.0

        utilisation = current / max_capacity

        if utilisation >= 1.0:
            return 0.0  # fully overloaded
        elif utilisation >= 0.9:
            return 3.0  # nearly full — heavy penalty
        elif utilisation >= 0.7:
            return 10.0
        elif utilisation >= 0.5:
            return 18.0
        elif utilisation >= 0.3:
            return 24.0
        elif utilisation >= 0.1:
            return 28.0
        else:
            return WORKLOAD_MAX  # completely free

    @staticmethod
    def _score_accuracy(
        resolution_rate: float,
        avg_csat: float,
        avg_response_time: float,
    ) -> float:
        """Score based on historical performance metrics (0–20).

        Combines resolution rate, CSAT, and response time.
        """
        # Resolution rate component (0–10)
        res_score = resolution_rate * 10.0

        # CSAT component (0–6) — scale 1–5 to 0–6
        csat_score = ((avg_csat - 1.0) / 4.0) * 6.0

        # Response time component (0–4) — faster is better
        # Under 5 min → full score; over 30 min → zero
        if avg_response_time <= 5.0:
            time_score = 4.0
        elif avg_response_time <= 10.0:
            time_score = 3.0
        elif avg_response_time <= 20.0:
            time_score = 1.5
        elif avg_response_time <= 30.0:
            time_score = 0.5
        else:
            time_score = 0.0

        return min(res_score + csat_score + time_score, ACCURACY_MAX)

    @staticmethod
    def _deterministic_jitter(ticket_id: str, agent_id: str) -> float:
        """Deterministic jitter: same ticket always gets same score per agent.

        GAP-027 FIX — prevents unstable / non-deterministic assignments.
        Uses SHA-256 hash of ``ticket_id:agent_id`` to produce a stable
        float in the range [0.0, 9.9].

        Args:
            ticket_id: The ticket being assigned.
            agent_id: The candidate agent.

        Returns:
            Jitter value between 0.0 and 9.9.
        """
        combined = f"{ticket_id}:{agent_id}"
        hash_value = int(hashlib.sha256(combined.encode()).hexdigest(), 16)
        return (hash_value % 100) / 10.0  # 0.0 to 9.9

    @staticmethod
    def _channel_bonus(agent: _AgentProfile, channel: str) -> float:
        """Small bonus for agents with channel-specific strengths."""
        bonus_skills = CHANNEL_SKILL_BONUS.get(channel, [])
        if not bonus_skills:
            return 0.0
        overlap = len(set(agent.skills) & set(bonus_skills))
        return min(overlap * 1.0, 3.0)

    # ════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ════════════════════════════════════════════════════════════════

    async def _assign_safe(
        self, request: TicketAssignmentRequest,
    ) -> TicketAssignmentResult:
        """Core assignment logic with full scoring pipeline."""
        agents = await self._get_available_agents(request.company_id)
        scores = await self._calculate_scores(request, agents)

        if not scores:
            return await self._fallback_assign(request)

        # Filter to available agents only
        available = [s for s in scores if s.is_available]

        if not available:
            logger.warning(
                "No available agents for ticket=%s (all overloaded), using best anyway",
                request.ticket_id,
            )
            available = scores  # BC-008: assign to best even if overloaded

        best = available[0]
        confidence = self._compute_confidence(scores)

        # Build alternatives list
        alternatives = [
            {
                "agent_id": s.agent_id,
                "agent_name": s.agent_name,
                "total_score": s.total_score,
            }
            for s in available[1:4]
        ]

        # Determine assignment method
        if best.total_score >= 60.0:
            method = AssignmentMethod.AI_SCORED.value
        elif best.total_score >= 30.0:
            method = AssignmentMethod.RULE_BASED.value
        else:
            method = AssignmentMethod.FALLBACK.value

        # Build human-readable reason
        reason = self._build_reason(request, best, method)

        return TicketAssignmentResult(
            ticket_id=request.ticket_id,
            assigned_agent_id=best.agent_id,
            assigned_agent_name=best.agent_name,
            assignment_method=method,
            total_score=round(best.total_score, 2),
            score_breakdown={
                "specialty": round(best.specialty_score, 2),
                "workload": round(best.workload_score, 2),
                "accuracy": round(best.accuracy_score, 2),
                "jitter": round(best.jitter_score, 2),
            },
            confidence=round(confidence, 4),
            alternatives=alternatives,
            assignment_time_ms=0.0,
            reason=reason,
        )

    async def _fallback_assign(
        self, request: TicketAssignmentRequest,
    ) -> TicketAssignmentResult:
        """Round-robin fallback when AI scoring is unavailable (BC-008)."""
        agents = await self._get_available_agents(request.company_id)
        if not agents:
            return TicketAssignmentResult(
                ticket_id=request.ticket_id,
                assigned_agent_id="",
                assigned_agent_name="",
                assignment_method=AssignmentMethod.FALLBACK.value,
                total_score=0.0,
                score_breakdown={},
                confidence=0.0,
                alternatives=[],
                assignment_time_ms=0.0,
                reason="No agents available — assignment queue pending",
            )

        # Simple round-robin: pick agent with fewest open tickets
        best = min(agents, key=lambda a: a.current_workload)

        return TicketAssignmentResult(
            ticket_id=request.ticket_id,
            assigned_agent_id=best.agent_id,
            assigned_agent_name=best.name,
            assignment_method=AssignmentMethod.FALLBACK.value,
            total_score=0.0,
            score_breakdown={},
            confidence=0.0,
            alternatives=[],
            assignment_time_ms=0.0,
            reason="Fallback: round-robin assignment (AI scoring unavailable)",
        )

    async def _get_available_agents(
        self, company_id: str,
    ) -> List[_AgentProfile]:
        """Fetch available agents.

        In production: queries the database via AssignmentService.
        In development: uses DEFAULT_AGENTS mock data.
        """
        # Try DB-backed agents first
        if self.assignment_service is not None and self.db is not None:
            try:
                self.assignment_service.company_id = company_id
                users = self.assignment_service._get_available_agents()
                if users:
                    return self._db_users_to_profiles(users)
            except Exception as exc:
                logger.warning(
                    "DB agent fetch failed, using defaults: %s", exc)

        # Fall back to mock agents with simulated workload
        return self._get_mock_agents_with_workload(company_id)

    def _db_users_to_profiles(self, users: list) -> List[_AgentProfile]:
        """Convert DB User objects to _AgentProfile."""
        profiles: List[_AgentProfile] = []
        for user in users:
            # Try to get skill data from user metadata or default
            skills = getattr(user, "skills", None)
            if skills and isinstance(skills, str):
                try:
                    skills = json.loads(skills)
                except (json.JSONDecodeError, TypeError):
                    skills = ["general"]
            elif not skills:
                skills = ["general"]

            profile = _AgentProfile(
                agent_id=str(user.id),
                name=getattr(
                    user,
                    "full_name",
                    None) or getattr(
                    user,
                    "email",
                    "Unknown"),
                skills=skills if isinstance(skills, list) else ["general"],
                specialty=getattr(user, "role", "general"),
                max_workload=15,
                current_workload=0,  # will be filled from ticket count
                resolution_rate=0.80,
                avg_csat=4.0,
                avg_response_time=10.0,
                is_active=getattr(user, "is_active", True),
            )
            profiles.append(profile)
        return profiles

    async def _get_mock_agents_with_workload(
        self, company_id: str,
    ) -> List[_AgentProfile]:
        """Return DEFAULT_AGENTS with simulated workload from Redis or random."""
        import random

        profiles = _build_agent_profiles()

        # Try to get cached workloads from Redis
        if self.redis is not None:
            try:
                workloads = await self.get_agent_workload(company_id)
                for profile in profiles:
                    if profile.agent_id in workloads:
                        w = workloads[profile.agent_id]
                        profile.current_workload = w.current_tickets
                    else:
                        # Simulate random workload for uncached agents
                        profile.current_workload = random.randint(
                            0, profile.max_workload // 2)
                return profiles
            except Exception:
                logger.debug(
                    "Redis workload fetch failed, using simulated values")

        # No Redis — simulate workload with deterministic seed based on
        # company_id
        seed = int(hashlib.md5(company_id.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        for profile in profiles:
            profile.current_workload = rng.randint(
                0, max(1, profile.max_workload // 2))

        return profiles

    async def _get_current_assignee(
        self, ticket_id: str, company_id: str,
    ) -> Optional[str]:
        """Look up the current assignee of a ticket."""
        if self.assignment_service is not None and self.db is not None:
            try:
                self.assignment_service.company_id = company_id
                from database.models.tickets import Ticket
                ticket = self.db.query(Ticket).filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == company_id,
                ).first()
                if ticket:
                    return str(
                        ticket.assigned_to) if ticket.assigned_to else None
            except Exception as exc:
                logger.debug("Could not fetch current assignee: %s", exc)
        return None

    @staticmethod
    def _compute_confidence(scores: List[AgentScore]) -> float:
        """Compute assignment confidence based on score spread.

        Higher spread between top-1 and top-2 → more confidence.
        """
        if not scores:
            return 0.0
        if len(scores) == 1:
            return 0.5  # only one agent — moderate confidence

        top = scores[0].total_score
        second = scores[1].total_score

        if top <= 0:
            return 0.0

        gap = top - second
        # Normalize: 10+ point gap → high confidence; <2 point gap → low
        confidence = min(gap / 10.0, 1.0)

        # Scale by absolute score quality
        if top >= 70:
            confidence *= 1.0
        elif top >= 40:
            confidence *= 0.8
        else:
            confidence *= 0.5

        return max(0.0, min(confidence, 1.0))

    @staticmethod
    def _build_reason(
        request: TicketAssignmentRequest,
        best: AgentScore,
        method: str,
    ) -> str:
        """Build a human-readable reason string for the assignment."""
        parts = [f"Intent: {request.intent_type}"]
        parts.append(f"Priority: {request.priority}")

        if best.skills_match:
            parts.append(
                f"Matching skills: {', '.join(best.skills_match[:3])}")

        parts.append(
            f"Agent workload: {best.current_workload}/{best.max_workload}"
        )
        parts.append(f"Historical accuracy: {best.historical_accuracy:.0%}")

        if request.sentiment_score < NEGATIVE_SENTIMENT_THRESHOLD:
            parts.append("Sentiment: negative (senior agent preferred)")

        if method == AssignmentMethod.AI_SCORED.value:
            prefix = "AI-scored assignment"
        elif method == AssignmentMethod.RULE_BASED.value:
            prefix = "Rule-based assignment"
        else:
            prefix = "Fallback assignment"

        return f"{prefix}. {'. '.join(parts)}"

    # ── high_parwa: Advanced Features ────────────────────────────

    async def _detect_variant(self, company_id: str) -> str:
        """Detect which variant a company is on (stub).

        In production, this queries the subscription / variant_service.
        """
        return VariantType.PARWA.value

    def _apply_trained_weights(
        self, weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply trained model weight adjustments (high_parwa only)."""
        adjusted = dict(weights)
        for factor, config in self._model_weights.items():
            mult_key = f"{factor}_mult"
            if mult_key in adjusted:
                adjusted[mult_key] *= config["weight"]
                adjusted[mult_key] = max(0.1, min(2.0, adjusted[mult_key]))
        return adjusted

    async def _apply_reassignment_optimization(
        self,
        scores: List[AgentScore],
        ticket_id: str,
    ) -> List[AgentScore]:
        """high_parwa: penalise agents who previously handled this ticket
        and had a negative outcome (escalation / reopened)."""
        # Stub — in production would query ticket outcome history
        return scores

    def _learn_weights(
        self, historical_data: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Learn weight adjustments from historical assignment outcomes.

        Analyses which factors most correlated with positive outcomes
        (resolved, high CSAT) and adjusts weights accordingly.

        Returns:
            Dict mapping factor name → weight delta.
        """
        adjustments: Dict[str, float] = {
            "specialty": 0.0,
            "workload": 0.0,
            "accuracy": 0.0,
        }

        if not historical_data:
            return adjustments

        # Analyse correlation between factor contributions and outcomes
        positive_outcomes = 0
        negative_outcomes = 0
        specialty_total_pos = 0.0
        workload_total_pos = 0.0
        accuracy_total_pos = 0.0
        specialty_total_neg = 0.0
        workload_total_neg = 0.0
        accuracy_total_neg = 0.0

        for record in historical_data:
            score_breakdown = record.get("score_breakdown", {})
            specialty = score_breakdown.get("specialty", 20.0)
            workload = score_breakdown.get("workload", 15.0)
            accuracy = score_breakdown.get("accuracy", 10.0)

            # Positive outcome: resolved + good CSAT
            outcome = record.get("outcome", "")
            csat = record.get("csat", 0)

            if outcome == "resolved" or csat >= 4.0:
                positive_outcomes += 1
                specialty_total_pos += specialty
                workload_total_pos += workload
                accuracy_total_pos += accuracy
            else:
                negative_outcomes += 1
                specialty_total_neg += specialty
                workload_total_neg += workload
                accuracy_total_neg += accuracy

        if positive_outcomes > 0 and negative_outcomes > 0:
            # If a factor was higher in positive outcomes → boost it
            avg_spec_pos = specialty_total_pos / positive_outcomes
            avg_spec_neg = specialty_total_neg / negative_outcomes
            avg_wl_pos = workload_total_pos / positive_outcomes
            avg_wl_neg = workload_total_neg / negative_outcomes
            avg_acc_pos = accuracy_total_pos / positive_outcomes
            avg_acc_neg = accuracy_total_neg / negative_outcomes

            # Small learning rate to avoid overshooting
            learning_rate = 0.05

            if avg_spec_pos > avg_spec_neg:
                adjustments["specialty"] = learning_rate
            else:
                adjustments["specialty"] = -learning_rate

            if avg_acc_pos > avg_acc_neg:
                adjustments["accuracy"] = learning_rate
            else:
                adjustments["accuracy"] = -learning_rate

            # Workload: if lower workload correlated with positive outcomes →
            # boost
            if avg_wl_pos < avg_wl_neg:
                adjustments["workload"] = learning_rate
            else:
                adjustments["workload"] = -learning_rate

        return adjustments

    @staticmethod
    def _estimate_model_accuracy(
        historical_data: List[Dict[str, Any]],
        trained: bool = False,
    ) -> float:
        """Estimate model accuracy from historical data.

        In production, this would run the scoring model on past data
        and compare predicted vs actual outcomes.
        """
        if not historical_data:
            return 0.0

        total = len(historical_data)
        positive = sum(
            1 for r in historical_data
            if r.get("outcome") == "resolved" or r.get("csat", 0) >= 4.0
        )

        base_accuracy = positive / total if total > 0 else 0.0

        if trained:
            # Simulate a small improvement from training
            return min(base_accuracy * 1.08, 0.99)
        return base_accuracy

    # ── Event recording ───────────────────────────────────────────

    async def _record_assignment_event(
        self,
        request: TicketAssignmentRequest,
        result: TicketAssignmentResult,
    ) -> None:
        """Store an assignment event in the in-memory history."""
        key = f"{request.company_id}:{request.ticket_id}"

        import uuid
        event = AssignmentEvent(
            event_id=str(uuid.uuid4()),
            ticket_id=request.ticket_id,
            company_id=request.company_id,
            agent_id=result.assigned_agent_id,
            agent_name=result.assigned_agent_name,
            method=result.assignment_method,
            score=result.total_score,
            reason=result.reason,
            assigned_at=result.assigned_at,
        )

        if key not in self._assignment_history:
            self._assignment_history[key] = []
        self._assignment_history[key].append(event)

        # Keep last 50 events per ticket to bound memory
        if len(self._assignment_history[key]) > 50:
            self._assignment_history[key] = self._assignment_history[key][-50:]

    # ── Cache invalidation ───────────────────────────────────────

    async def invalidate_workload_cache(self, company_id: str) -> bool:
        """Invalidate the workload cache for a company.

        Call this when an agent's workload changes (ticket assigned/closed).
        """
        if self.redis is None:
            return False

        cache_key = f"workload:{company_id}"
        try:
            await self.redis.delete(cache_key)
            logger.debug(
                "Invalidated workload cache for company=%s",
                company_id)
            return True
        except Exception:
            logger.warning(
                "Failed to invalidate workload cache for company=%s",
                company_id)
            return False
