"""
PARWA AI Assignment Scoring Service

Real 5-factor scoring algorithm for intelligent ticket assignment.
Replaces the stub implementation in assignment_service.py.

5-Factor Scoring Model:
1. Expertise Match (40 pts) - Category/intent matches agent specialty
2. Workload Balance (30 pts) - Fewer open tickets = higher score
3. Performance History (20 pts) - Resolution rate, CSAT, confidence
4. Response Time History (15 pts) - SLA compliance rate
5. Availability (10 pts) - Online/active status

Total: 115 pts max, normalized to 0.0-1.0

Building Codes: BC-001 (multi-tenant), BC-012 (graceful errors)
"""

from __future__ import annotations
from collections import OrderedDict

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("assignment_scoring_service")


# ══════════════════════════════════════════════════════════════════
# SCORING WEIGHTS AND CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Factor weights (sum to 115 for normalization)
FACTOR_WEIGHTS = {
    "expertise": 40,      # Match between ticket category and agent specialty
    "workload": 30,       # Current open ticket count (inverse)
    "performance": 20,    # Historical resolution rate + CSAT
    "response_time": 15,  # SLA compliance rate
    "availability": 10,   # Online status bonus
}

MAX_SCORE = sum(FACTOR_WEIGHTS.values())  # 115

# Workload thresholds
MAX_OPEN_TICKETS = 20  # Beyond this, workload score is 0
OPTIMAL_WORKLOAD = 5   # At or below this, full workload score

# Performance thresholds
MIN_RESOLUTION_RATE = 50.0   # Below this, performance penalty
EXCELLENT_RESOLUTION_RATE = 90.0  # Above this, bonus
MIN_CSAT = 3.0          # Below this, performance penalty
EXCELLENT_CSAT = 4.5    # Above this, bonus

# SLA compliance thresholds
MIN_SLA_COMPLIANCE = 70.0    # Below this, SLA penalty
EXCELLENT_SLA_COMPLIANCE = 95.0  # Above this, bonus


class AssignmentScoringService:
    """AI-powered ticket assignment scoring service.

    Provides real 5-factor scoring for intelligent agent selection.
    All queries are scoped by company_id (BC-001).
    """

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── PUBLIC API ─────────────────────────────────────────────────────

    def calculate_scores(
        self,
        ticket_id: str,
        candidate_agent_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Calculate assignment scores for all candidates.

        Args:
            ticket_id: Ticket to assign
            candidate_agent_ids: Optional list of specific agents to score.
                                 If None, scores all available agents.

        Returns:
            Dict with:
                - ticket_id: str
                - candidates: List of scored candidates
                - recommended_assignee: Best match with score breakdown
                - scoring_method: "5-factor-ai"
        """
        from database.models.tickets import Ticket
        from database.models.core import User

        # Get ticket
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()

        if not ticket:
            return {
                "ticket_id": ticket_id,
                "candidates": [],
                "recommended_assignee": None,
                "scoring_method": "5-factor-ai",
                "error": "Ticket not found",
            }

        # Get candidate agents
        if candidate_agent_ids:
            agents = self.db.query(User).filter(
                User.id.in_(candidate_agent_ids),
                User.company_id == self.company_id,
                User.is_active,
            ).all()
        else:
            agents = self._get_available_agents()

        # Score each agent
        scored_candidates = []
        for agent in agents:
            score_result = self._score_agent(agent, ticket)
            scored_candidates.append(score_result)

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)

        # Get best match
        best_match = scored_candidates[0] if scored_candidates else None

        return {
            "ticket_id": ticket_id,
            "ticket_category": ticket.category,
            "ticket_priority": ticket.priority,
            "candidates": scored_candidates,
            "recommended_assignee": best_match,
            "scoring_method": "5-factor-ai",
        }

    def get_best_assignee(
        self,
        ticket_id: str,
        min_score: float = 0.3,
    ) -> Optional[Dict[str, Any]]:
        """Get the best assignee for a ticket.

        Args:
            ticket_id: Ticket to assign
            min_score: Minimum score threshold (0.0-1.0)

        Returns:
            Best candidate dict or None if no agent meets threshold
        """
        result = self.calculate_scores(ticket_id)

        if not result.get("recommended_assignee"):
            return None

        best = result["recommended_assignee"]
        if best["normalized_score"] < min_score:
            return None

        return best

    def explain_score(
        self,
        ticket_id: str,
        agent_id: str,
    ) -> Dict[str, Any]:
        """Explain the scoring breakdown for a specific agent-ticket pair.

        Args:
            ticket_id: Ticket ID
            agent_id: Agent ID

        Returns:
            Detailed score breakdown with explanations
        """
        from database.models.tickets import Ticket
        from database.models.core import User

        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()

        agent = self.db.query(User).filter(
            User.id == agent_id,
            User.company_id == self.company_id,
        ).first()

        if not ticket or not agent:
            return {
                "error": "Ticket or agent not found",
                "ticket_id": ticket_id,
                "agent_id": agent_id,
            }

        return self._score_agent(agent, ticket, include_explanation=True)

    # ── PRIVATE SCORING METHODS ─────────────────────────────────────────

    def _score_agent(
        self,
        agent: Any,
        ticket: Any,
        include_explanation: bool = False,
    ) -> Dict[str, Any]:
        """Calculate full score for an agent-ticket pair.

        Args:
            agent: User ORM object (the agent)
            ticket: Ticket ORM object
            include_explanation: Include detailed explanations

        Returns:
            Score dict with breakdown and total
        """
        # Get agent metrics
        metrics = self._get_agent_metrics(agent.id)
        workload = self._get_agent_workload(agent.id)

        # Calculate each factor
        expertise_score, expertise_details = self._score_expertise(
            agent, ticket, metrics
        )
        workload_score, workload_details = self._score_workload(workload)
        performance_score, performance_details = self._score_performance(
            metrics)
        response_score, response_details = self._score_response_time(metrics)
        availability_score, availability_details = self._score_availability(
            agent)

        # Total raw score
        total_raw = (
            expertise_score +
            workload_score +
            performance_score +
            response_score +
            availability_score
        )

        # Normalize to 0.0-1.0
        normalized = round(total_raw / MAX_SCORE, 4)

        result = {
            "agent_id": agent.id,
            "agent_name": getattr(agent, 'full_name', None) or agent.email,
            "raw_score": total_raw,
            "normalized_score": normalized,
            "total_score": normalized,  # For compatibility
            "score_breakdown": {
                "expertise": {
                    "raw": expertise_score,
                    "max": FACTOR_WEIGHTS["expertise"],
                    "percentage": round(expertise_score / FACTOR_WEIGHTS["expertise"] * 100, 1),
                },
                "workload": {
                    "raw": workload_score,
                    "max": FACTOR_WEIGHTS["workload"],
                    "percentage": round(workload_score / FACTOR_WEIGHTS["workload"] * 100, 1),
                    "current_tickets": workload,
                },
                "performance": {
                    "raw": performance_score,
                    "max": FACTOR_WEIGHTS["performance"],
                    "percentage": round(performance_score / FACTOR_WEIGHTS["performance"] * 100, 1),
                },
                "response_time": {
                    "raw": response_score,
                    "max": FACTOR_WEIGHTS["response_time"],
                    "percentage": round(response_score / FACTOR_WEIGHTS["response_time"] * 100, 1),
                },
                "availability": {
                    "raw": availability_score,
                    "max": FACTOR_WEIGHTS["availability"],
                    "percentage": round(availability_score / FACTOR_WEIGHTS["availability"] * 100, 1),
                },
            },
        }

        if include_explanation:
            result["explanations"] = {
                "expertise": expertise_details,
                "workload": workload_details,
                "performance": performance_details,
                "response_time": response_details,
                "availability": availability_details,
            }

        return result

    def _score_expertise(
        self,
        agent: Any,
        ticket: Any,
        metrics: Dict[str, Any],
    ) -> Tuple[float, str]:
        """Score expertise match between agent and ticket.

        Factors:
        - Agent specialty vs ticket category
        - Agent's historical performance on this category
        - Agent's skills/permissions

        Returns:
            Tuple of (score, explanation)
        """
        score = 0.0
        explanations = []

        # Get agent specialty from metadata or profile
        agent_specialty = getattr(agent, 'specialty', None)
        if not agent_specialty:
            # Try metadata
            metadata = getattr(agent, 'metadata_json', None)
            if metadata:
                try:
                    import json
                    meta = json.loads(metadata) if isinstance(
                        metadata, str) else metadata
                    agent_specialty = meta.get('specialty')
                except BaseException:
                    pass

        ticket_category = ticket.category

        # Direct specialty match (max points)
        if agent_specialty and ticket_category:
            if agent_specialty.lower() == ticket_category.lower():
                score = FACTOR_WEIGHTS["expertise"]
                explanations.append(
                    f"Direct specialty match: {agent_specialty}")
            elif ticket_category.lower() in str(agent_specialty).lower():
                # Partial match
                score = FACTOR_WEIGHTS["expertise"] * 0.7
                explanations.append(
                    f"Partial specialty match: {agent_specialty} ~= {ticket_category}")
            else:
                # No match - base score only
                score = FACTOR_WEIGHTS["expertise"] * 0.2
                explanations.append(
                    f"No specialty match (agent: {agent_specialty}, ticket: {ticket_category})")
        else:
            # No specialty info - give base score
            score = FACTOR_WEIGHTS["expertise"] * 0.3
            explanations.append("No specialty information available")

        # Bonus for historical performance on this category
        category_metrics = metrics.get("category_performance", {})
        if ticket_category and ticket_category in category_metrics:
            cat_rate = category_metrics[ticket_category].get(
                "resolution_rate", 0)
            if cat_rate >= EXCELLENT_RESOLUTION_RATE:
                score = min(score + 5, FACTOR_WEIGHTS["expertise"])
                explanations.append(
                    f"Excellent history on {ticket_category}: {cat_rate}% resolution")
            elif cat_rate >= MIN_RESOLUTION_RATE:
                score = min(score + 2, FACTOR_WEIGHTS["expertise"])
                explanations.append(
                    f"Good history on {ticket_category}: {cat_rate}% resolution")

        return score, "; ".join(
            explanations) if explanations else "Base expertise score"

    def _score_workload(
        self,
        current_tickets: int,
    ) -> Tuple[float, str]:
        """Score based on current workload (inverse - lower is better).

        Uses a smooth decay function:
        - 0-5 tickets: Full score
        - 6-20 tickets: Linear decay
        - 20+ tickets: Zero score

        Returns:
            Tuple of (score, explanation)
        """
        if current_tickets <= OPTIMAL_WORKLOAD:
            score = FACTOR_WEIGHTS["workload"]
            explanation = f"Optimal workload: {current_tickets} open tickets"
        elif current_tickets >= MAX_OPEN_TICKETS:
            score = 0.0
            explanation = f"At capacity: {current_tickets} open tickets (max: {MAX_OPEN_TICKETS})"
        else:
            # Linear decay
            ratio = (MAX_OPEN_TICKETS - current_tickets) / \
                (MAX_OPEN_TICKETS - OPTIMAL_WORKLOAD)
            score = FACTOR_WEIGHTS["workload"] * ratio
            explanation = f"Moderate workload: {current_tickets} open tickets"

        return score, explanation

    def _score_performance(
        self,
        metrics: Dict[str, Any],
    ) -> Tuple[float, str]:
        """Score based on historical performance metrics.

        Factors:
        - Resolution rate (last 30 days)
        - Average CSAT score
        - Average AI confidence

        Returns:
            Tuple of (score, explanation)
        """
        explanations = []
        score = 0.0

        resolution_rate = metrics.get("resolution_rate")
        avg_csat = metrics.get("avg_csat")
        avg_confidence = metrics.get("avg_confidence")

        # Resolution rate scoring (10 points max)
        if resolution_rate is not None:
            if resolution_rate >= EXCELLENT_RESOLUTION_RATE:
                score += 10
                explanations.append(
                    f"Excellent resolution rate: {resolution_rate}%")
            elif resolution_rate >= MIN_RESOLUTION_RATE:
                # Scale between min and excellent
                ratio = (resolution_rate - MIN_RESOLUTION_RATE) / \
                    (EXCELLENT_RESOLUTION_RATE - MIN_RESOLUTION_RATE)
                score += 5 + (5 * ratio)
                explanations.append(
                    f"Good resolution rate: {resolution_rate}%")
            else:
                # Below minimum - reduced score
                score += max(0, resolution_rate / MIN_RESOLUTION_RATE * 5)
                explanations.append(
                    f"Below average resolution rate: {resolution_rate}%")
        else:
            score += 5  # Default for no data
            explanations.append("No resolution rate data")

        # CSAT scoring (5 points max)
        if avg_csat is not None:
            if avg_csat >= EXCELLENT_CSAT:
                score += 5
                explanations.append(f"Excellent CSAT: {avg_csat}")
            elif avg_csat >= MIN_CSAT:
                ratio = (avg_csat - MIN_CSAT) / (EXCELLENT_CSAT - MIN_CSAT)
                score += 2.5 + (2.5 * ratio)
                explanations.append(f"Good CSAT: {avg_csat}")
            else:
                score += max(0, avg_csat / MIN_CSAT * 2)
                explanations.append(f"Below average CSAT: {avg_csat}")
        else:
            score += 2.5  # Default for no data
            explanations.append("No CSAT data")

        # Confidence scoring (5 points max)
        if avg_confidence is not None:
            # Confidence is 0-100
            normalized_conf = avg_confidence / 100.0
            score += 5 * normalized_conf
            explanations.append(f"AI confidence: {avg_confidence}%")
        else:
            score += 2.5  # Default for no data
            explanations.append("No confidence data")

        return score, "; ".join(explanations)

    def _score_response_time(
        self,
        metrics: Dict[str, Any],
    ) -> Tuple[float, str]:
        """Score based on SLA compliance and response time history.

        Factors:
        - SLA compliance rate
        - Average first response time

        Returns:
            Tuple of (score, explanation)
        """
        explanations = []
        score = 0.0

        sla_compliance = metrics.get("sla_compliance_rate")
        avg_response_time = metrics.get("avg_response_time_minutes")

        # SLA compliance scoring (10 points max)
        if sla_compliance is not None:
            if sla_compliance >= EXCELLENT_SLA_COMPLIANCE:
                score += 10
                explanations.append(
                    f"Excellent SLA compliance: {sla_compliance}%")
            elif sla_compliance >= MIN_SLA_COMPLIANCE:
                ratio = (sla_compliance - MIN_SLA_COMPLIANCE) / \
                    (EXCELLENT_SLA_COMPLIANCE - MIN_SLA_COMPLIANCE)
                score += 5 + (5 * ratio)
                explanations.append(f"Good SLA compliance: {sla_compliance}%")
            else:
                score += max(0, sla_compliance / MIN_SLA_COMPLIANCE * 5)
                explanations.append(
                    f"Below average SLA compliance: {sla_compliance}%")
        else:
            score += 5  # Default for no data
            explanations.append("No SLA compliance data")

        # Response time scoring (5 points max)
        if avg_response_time is not None:
            # Lower is better; target is under 5 minutes
            if avg_response_time <= 5:
                score += 5
                explanations.append(
                    f"Excellent response time: {
                        avg_response_time:.1f} min avg")
            elif avg_response_time <= 15:
                ratio = (15 - avg_response_time) / 10
                score += 2.5 + (2.5 * ratio)
                explanations.append(
                    f"Good response time: {
                        avg_response_time:.1f} min avg")
            elif avg_response_time <= 60:
                ratio = (60 - avg_response_time) / 45
                score += 2.5 * ratio
                explanations.append(
                    f"Average response time: {
                        avg_response_time:.1f} min avg")
            else:
                score += 0
                explanations.append(
                    f"Slow response time: {
                        avg_response_time:.1f} min avg")
        else:
            score += 2.5  # Default for no data
            explanations.append("No response time data")

        return score, "; ".join(explanations)

    def _score_availability(
        self,
        agent: Any,
    ) -> Tuple[float, str]:
        """Score based on agent availability status.

        Factors:
        - Is the agent active/online?
        - Is the agent currently on a call/chat?

        Returns:
            Tuple of (score, explanation)
        """
        # Check agent status
        agent_status = getattr(agent, 'status', 'active')

        # For AI agents, check if status is 'active'
        # For human agents, check is_active
        is_active = getattr(agent, 'is_active', True)

        if agent_status == 'active' and is_active:
            score = FACTOR_WEIGHTS["availability"]
            explanation = "Agent is active and available"
        elif agent_status == 'paused':
            score = FACTOR_WEIGHTS["availability"] * 0.3
            explanation = "Agent is paused"
        elif agent_status == 'training':
            score = FACTOR_WEIGHTS["availability"] * 0.5
            explanation = "Agent is in training mode"
        elif not is_active:
            score = 0.0
            explanation = "Agent is not active"
        else:
            score = FACTOR_WEIGHTS["availability"] * 0.7
            explanation = f"Agent status: {agent_status}"

        return score, explanation

    # ── DATA RETRIEVAL METHODS ─────────────────────────────────────────

    def _get_available_agents(self) -> List[Any]:
        """Get all available agents for assignment."""
        from database.models.core import User
        from database.models.agent import Agent

        # Get both human agents (Users) and AI agents
        human_agents = self.db.query(User).filter(
            User.company_id == self.company_id,
            User.is_active,
        ).all()

        ai_agents = self.db.query(Agent).filter(
            Agent.company_id == self.company_id,
            Agent.status == 'active',
        ).all()

        # Return combined list (prefer AI agents for auto-assignment)
        return ai_agents + human_agents

    def _get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """Get performance metrics for an agent.

        Uses AgentMetricsService if available, otherwise computes directly.
        """
        try:
            from app.services.agent_metrics_service import AgentMetricsService

            metrics_svc = AgentMetricsService(self.db)
            result = metrics_svc.get_metrics(
                agent_id=agent_id,
                company_id=self.company_id,
                period="30d",
            )

            summary = result.get("summary", {})

            return {
                "resolution_rate": summary.get("avg_resolution_rate"),
                "avg_csat": summary.get("avg_csat"),
                "avg_confidence": summary.get("avg_confidence"),
                "escalation_rate": summary.get("avg_escalation_rate"),
                "total_tickets": summary.get("total_tickets", 0),
                "sla_compliance_rate": self._compute_sla_compliance(agent_id),
                "avg_response_time_minutes": self._compute_avg_response_time(agent_id),
                "category_performance": self._compute_category_performance(agent_id),
            }

        except Exception as exc:
            logger.warning(
                "get_agent_metrics_fallback",
                company_id=self.company_id,
                agent_id=agent_id,
                error=str(exc),
            )
            # Fallback to direct computation
            return self._compute_agent_metrics_direct(agent_id)

    def _get_agent_workload(self, agent_id: str) -> int:
        """Get current open ticket count for an agent."""
        from database.models.tickets import Ticket, TicketStatus

        try:
            return self.db.query(func.count(Ticket.id)).filter(
                Ticket.company_id == self.company_id,
                Ticket.assigned_to == agent_id,
                Ticket.status.in_([
                    TicketStatus.open.value,
                    TicketStatus.assigned.value,
                    TicketStatus.in_progress.value,
                    TicketStatus.awaiting_client.value,
                ]),
            ).scalar() or 0

        except Exception:
            return 0

    def _compute_sla_compliance(self, agent_id: str) -> Optional[float]:
        """Compute SLA compliance rate for an agent."""
        from database.models.tickets import Ticket, SLATimer, TicketStatus

        try:
            # Get resolved tickets with SLA info
            resolved_with_sla = self.db.query(Ticket).join(
                SLATimer, SLATimer.ticket_id == Ticket.id
            ).filter(
                Ticket.company_id == self.company_id,
                Ticket.assigned_to == agent_id,
                Ticket.status.in_([TicketStatus.resolved.value, TicketStatus.closed.value]),
            ).count()

            breached = self.db.query(Ticket).join(
                SLATimer, SLATimer.ticket_id == Ticket.id
            ).filter(
                Ticket.company_id == self.company_id,
                Ticket.assigned_to == agent_id,
                SLATimer.is_breached,
            ).count()

            if resolved_with_sla > 0:
                return round((resolved_with_sla - breached) /
                             resolved_with_sla * 100, 1)

            return None

        except Exception:
            return None

    def _compute_avg_response_time(self, agent_id: str) -> Optional[float]:
        """Compute average first response time in minutes for an agent."""
        from database.models.tickets import Ticket

        try:
            since = datetime.now(timezone.utc) - timedelta(days=30)

            tickets = self.db.query(Ticket).filter(
                Ticket.company_id == self.company_id,
                Ticket.assigned_to == agent_id,
                Ticket.first_response_at.isnot(None),
                Ticket.created_at >= since,
            ).all()

            if not tickets:
                return None

            times = []
            for t in tickets:
                if t.first_response_at and t.created_at:
                    minutes = (
                        t.first_response_at - t.created_at).total_seconds() / 60
                    times.append(minutes)

            return round(sum(times) / len(times), 1) if times else None

        except Exception:
            return None

    def _compute_category_performance(self, agent_id: str) -> Dict[str, Any]:
        """Compute performance metrics by ticket category."""
        from database.models.tickets import Ticket, TicketStatus

        try:
            since = datetime.now(timezone.utc) - timedelta(days=30)

            # Group by category
            tickets = self.db.query(Ticket).filter(
                Ticket.company_id == self.company_id,
                Ticket.assigned_to == agent_id,
                Ticket.created_at >= since,
                Ticket.category.isnot(None),
            ).all()

            category_stats = {}
            for t in tickets:
                cat = t.category
                if cat not in category_stats:
                    category_stats[cat] = {"total": 0, "resolved": 0}
                category_stats[cat]["total"] += 1
                if t.status in [
                    TicketStatus.resolved.value,
                        TicketStatus.closed.value]:
                    category_stats[cat]["resolved"] += 1

            result = {}
            for cat, stats in category_stats.items():
                if stats["total"] > 0:
                    result[cat] = {
                        "total": stats["total"],
                        "resolved": stats["resolved"],
                        "resolution_rate": round(
                            stats["resolved"] /
                            stats["total"] *
                            100,
                            1),
                    }

            return result

        except Exception:
            return {}

    def _compute_agent_metrics_direct(self, agent_id: str) -> Dict[str, Any]:
        """Fallback direct computation of agent metrics."""
        from database.models.tickets import Ticket, TicketFeedback, TicketStatus

        try:
            since = datetime.now(timezone.utc) - timedelta(days=30)

            # Get tickets assigned to this agent
            tickets = self.db.query(Ticket).filter(
                Ticket.company_id == self.company_id,
                Ticket.assigned_to == agent_id,
                Ticket.created_at >= since,
            ).all()

            if not tickets:
                return {
                    "resolution_rate": None,
                    "avg_csat": None,
                    "avg_confidence": None,
                    "total_tickets": 0,
                }

            total = len(tickets)
            resolved = sum(
                1 for t in tickets if t.status in [
                    TicketStatus.resolved.value,
                    TicketStatus.closed.value])
            resolution_rate = round(
                resolved / total * 100,
                1) if total > 0 else None

            # Get CSAT
            ticket_ids = [t.id for t in tickets]
            avg_csat = self.db.query(func.avg(TicketFeedback.rating)).filter(
                TicketFeedback.ticket_id.in_(ticket_ids),
            ).scalar()

            # Get confidence
            confidences = [
                t.ai_confidence for t in tickets if t.ai_confidence is not None]
            avg_confidence = round(
                sum(confidences) / len(confidences),
                1) if confidences else None

            return {
                "resolution_rate": resolution_rate,
                "avg_csat": round(
                    float(avg_csat),
                    2) if avg_csat else None,
                "avg_confidence": avg_confidence,
                "total_tickets": total,
                "sla_compliance_rate": self._compute_sla_compliance(agent_id),
                "avg_response_time_minutes": self._compute_avg_response_time(agent_id),
                "category_performance": self._compute_category_performance(agent_id),
            }

        except Exception as exc:
            logger.error(
                "compute_agent_metrics_direct_error",
                company_id=self.company_id,
                agent_id=agent_id,
                error=str(exc),
            )
            return {
                "resolution_rate": None,
                "avg_csat": None,
                "avg_confidence": None,
                "total_tickets": 0,
            }


# ══════════════════════════════════════════════════════════════════
# SERVICE FACTORY
# ══════════════════════════════════════════════════════════════════


_SERVICE_CACHE_MAX_SIZE = 1000
_service_cache: OrderedDict[str, AssignmentScoringService] = OrderedDict()


def get_assignment_scoring_service(
    db: Session,
    company_id: str,
) -> AssignmentScoringService:
    """Get or create an AssignmentScoringService for a tenant (LRU cache).

    Args:
        db: Database session
        company_id: Tenant identifier (BC-001)

    Returns:
        AssignmentScoringService instance
    """
    cache_key = f"{company_id}:{id(db)}"

    if cache_key not in _service_cache:
        if len(_service_cache) >= _SERVICE_CACHE_MAX_SIZE:
            _service_cache.popitem(last=False)
        _service_cache[cache_key] = AssignmentScoringService(db, company_id)
    else:
        _service_cache.move_to_end(cache_key)

    return _service_cache[cache_key]


__all__ = [
    "AssignmentScoringService",
    "get_assignment_scoring_service",
    "FACTOR_WEIGHTS",
    "MAX_SCORE",
]
