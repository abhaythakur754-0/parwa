"""
PARWA Agent Dashboard Service (F-097)

Card-based dashboard data for all AI agents. Each card shows real-time
status, specialty, performance metrics (resolution rate, CSAT trend,
avg confidence), sparkline data, and quick-action affordances.

Methods:
- get_agent_cards()          — All agent cards with status, metrics, actions
- get_agent_card()           — Single agent card detail
- get_agent_status_counts()  — Counts by status for filter chips
- get_agent_realtime_metrics() — Latest metrics for Socket.io push
- pause_agent()              — Pause an agent
- resume_agent()             — Resume a paused agent

Building Codes: BC-001 (multi-tenant), BC-005 (real-time / Socket.io),
               BC-007 (AI model availability), BC-012 (graceful errors)
"""

from __future__ import annotations
from collections import OrderedDict

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.logger import get_logger

logger = get_logger("agent_dashboard_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

SPARKLINE_DAYS = 14

# Agent statuses considered "running" — these cannot be paused
_ACTIVE_STATUSES = ("active", "training")

# Transitions allowed for pause / resume
_PAUSE_ALLOWED_FROM = ("active",)
_RESUME_ALLOWED_FROM = ("paused",)


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class AgentDashboardService:
    """Agent Dashboard Service (F-097).

    Provides card-based dashboard data for all AI agents scoped to
    a single tenant.

    BC-001: All methods scoped by company_id.
    BC-005: Emits Socket.io events for status changes and metrics.
    BC-007: Agent status tied to model availability.
    BC-012: Graceful error handling throughout.
    """

    def __init__(self, company_id: str):
        self.company_id = company_id

    # ── Public API ────────────────────────────────────────────

    def get_agent_cards(
        self,
        db: Session,
        status_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return all agent cards with status, metrics, and quick actions.

        Args:
            db: Database session.
            status_filter: Optional status to filter by.

        Returns:
            Dict with 'cards' list and 'status_counts'.
        """
        from database.models.agent import Agent

        try:
            query = db.query(Agent).filter(
                Agent.company_id == self.company_id,
                Agent.status != "deprovisioned",
            )

            if status_filter:
                query = query.filter(Agent.status == status_filter)

            agents = query.order_by(Agent.created_at.desc()).all()

            cards: List[Dict[str, Any]] = []
            for agent in agents:
                card = self._build_agent_card(agent, db)
                cards.append(card)

            status_counts = self.get_agent_status_counts(db)

            return {
                "cards": cards,
                "status_counts": status_counts,
            }

        except Exception as exc:
            logger.error(
                "get_agent_cards_error",
                company_id=self.company_id,
                error=str(exc),
            )
            return {
                "cards": [],
                "status_counts": {
                    "active": 0, "training": 0, "paused": 0,
                    "error": 0, "cold_start": 0, "total": 0,
                },
            }

    def get_agent_card(
        self,
        agent_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Return a single agent card detail.

        Args:
            agent_id: Agent UUID.
            db: Database session.

        Returns:
            Detailed agent card dict.

        Raises:
            NotFoundError: If agent not found.
        """
        from database.models.agent import Agent, InstructionSet
        from app.exceptions import NotFoundError

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.company_id == self.company_id,
        ).first()

        if not agent:
            raise NotFoundError(
                message="Agent not found",
                details={"agent_id": agent_id},
            )

        card = self._build_agent_card(agent, db)

        # Enrich with detail-level data
        channels_data = self._parse_json(agent.channels)
        permissions_data = self._parse_json(agent.permissions)

        card["channels"] = channels_data
        card["permissions"] = permissions_data

        # Setup status for non-active agents
        if agent.status in ("initializing", "training", "error"):
            try:
                from app.services.agent_provisioning_service import (
                    get_agent_provisioning_service,
                )
                svc = get_agent_provisioning_service(self.company_id)
                card["setup_status"] = svc.get_setup_status(agent_id, db)
            except Exception:
                card["setup_status"] = None

        # Active instruction set
        active_set = db.query(InstructionSet).filter(
            InstructionSet.agent_id == agent_id,
            InstructionSet.company_id == self.company_id,
            InstructionSet.status == "active",
        ).first()

        if active_set:
            card["active_instruction_set"] = {
                "id": active_set.id,
                "name": active_set.name,
                "version": active_set.version,
            }

        return card

    def get_agent_status_counts(
        self,
        db: Session,
    ) -> Dict[str, int]:
        """Return agent counts grouped by status.

        Args:
            db: Database session.

        Returns:
            Dict with counts per status and total.
        """
        from database.models.agent import Agent

        try:
            rows = db.query(
                Agent.status, func.count(Agent.id),
            ).filter(
                Agent.company_id == self.company_id,
                Agent.status != "deprovisioned",
            ).group_by(Agent.status).all()

            counts: Dict[str, int] = {
                "active": 0,
                "training": 0,
                "paused": 0,
                "error": 0,
                "cold_start": 0,
            }

            total = 0
            for status, count in rows:
                total += count
                if status in counts:
                    counts[status] = count
                elif status == "initializing":
                    # Treat initializing as cold_start in dashboard
                    counts["cold_start"] += count

            counts["total"] = total
            return counts

        except Exception as exc:
            logger.error(
                "get_agent_status_counts_error",
                company_id=self.company_id,
                error=str(exc),
            )
            return {
                "active": 0, "training": 0, "paused": 0,
                "error": 0, "cold_start": 0, "total": 0,
            }

    def get_agent_realtime_metrics(
        self,
        agent_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Get latest metrics for a single agent (Socket.io push).

        Args:
            agent_id: Agent UUID.
            db: Database session.

        Returns:
            Metrics dict suitable for agent:metrics_updated event.

        Raises:
            NotFoundError: If agent not found.
        """
        from database.models.agent import Agent
        from app.exceptions import NotFoundError

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.company_id == self.company_id,
        ).first()

        if not agent:
            raise NotFoundError(
                message="Agent not found",
                details={"agent_id": agent_id},
            )

        metrics = self._compute_metrics(agent, db)

        return {
            "agent_id": agent.id,
            "company_id": self.company_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metrics,
        }

    def pause_agent(
        self,
        agent_id: str,
        db: Session,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pause an active agent.

        Only agents in 'active' status can be paused.
        Emits agent:status_changed Socket.io event.

        Args:
            agent_id: Agent UUID.
            db: Database session.
            user_id: Optional user performing the action.

        Returns:
            Dict with agent_id, previous_status, new_status, message.

        Raises:
            NotFoundError: If agent not found.
            ValidationError: If agent cannot be paused.
        """
        from database.models.agent import Agent
        from app.exceptions import NotFoundError, ValidationError

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.company_id == self.company_id,
        ).first()

        if not agent:
            raise NotFoundError(
                message="Agent not found",
                details={"agent_id": agent_id},
            )

        if agent.status not in _PAUSE_ALLOWED_FROM:
            raise ValidationError(
                message=(
                    f"Cannot pause agent in '{
                        agent.status}' status. " f"Only agents in {
                        list(_PAUSE_ALLOWED_FROM)} can be paused."),
                details={
                    "agent_id": agent_id,
                    "current_status": agent.status,
                    "allowed_statuses": list(_PAUSE_ALLOWED_FROM),
                },
            )

        previous_status = agent.status
        now = datetime.now(timezone.utc)
        agent.status = "paused"
        agent.updated_at = now
        db.flush()

        logger.info(
            "agent_paused",
            company_id=self.company_id,
            agent_id=agent_id,
            previous_status=previous_status,
            user_id=user_id,
        )

        # Emit Socket.io event (BC-005) — fire-and-forget style
        self._emit_status_change(
            agent_id=agent_id,
            previous_status=previous_status,
            new_status="paused",
            user_id=user_id,
        )

        return {
            "agent_id": agent.id,
            "previous_status": previous_status,
            "new_status": "paused",
            "message": f"Agent '{agent.name}' has been paused",
        }

    def resume_agent(
        self,
        agent_id: str,
        db: Session,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resume a paused agent.

        Only agents in 'paused' status can be resumed.
        Emits agent:status_changed Socket.io event.

        Args:
            agent_id: Agent UUID.
            db: Database session.
            user_id: Optional user performing the action.

        Returns:
            Dict with agent_id, previous_status, new_status, message.

        Raises:
            NotFoundError: If agent not found.
            ValidationError: If agent cannot be resumed.
        """
        from database.models.agent import Agent
        from app.exceptions import NotFoundError, ValidationError

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.company_id == self.company_id,
        ).first()

        if not agent:
            raise NotFoundError(
                message="Agent not found",
                details={"agent_id": agent_id},
            )

        if agent.status not in _RESUME_ALLOWED_FROM:
            raise ValidationError(
                message=(
                    f"Cannot resume agent in '{
                        agent.status}' status. " f"Only agents in {
                        list(_RESUME_ALLOWED_FROM)} can be resumed."),
                details={
                    "agent_id": agent_id,
                    "current_status": agent.status,
                    "allowed_statuses": list(_RESUME_ALLOWED_FROM),
                },
            )

        previous_status = agent.status
        now = datetime.now(timezone.utc)
        agent.status = "active"
        agent.updated_at = now
        db.flush()

        logger.info(
            "agent_resumed",
            company_id=self.company_id,
            agent_id=agent_id,
            previous_status=previous_status,
            user_id=user_id,
        )

        # Emit Socket.io event (BC-005)
        self._emit_status_change(
            agent_id=agent_id,
            previous_status=previous_status,
            new_status="active",
            user_id=user_id,
        )

        return {
            "agent_id": agent.id,
            "previous_status": previous_status,
            "new_status": "active",
            "message": f"Agent '{agent.name}' has been resumed",
        }

    # ── Card Builder ──────────────────────────────────────────

    def _build_agent_card(
        self,
        agent: Any,
        db: Session,
    ) -> Dict[str, Any]:
        """Build a dashboard card dict from an Agent ORM object.

        Computes metrics, sparkline data, and quick-action
        affordances for the agent.

        Args:
            agent: Agent ORM object.
            db: Database session.

        Returns:
            Card dict ready for JSON serialization.
        """
        metrics = self._compute_metrics(agent, db)
        sparkline = self._compute_sparkline(agent, db)
        quick_actions = self._compute_quick_actions(agent)

        # Map model-level status to dashboard status
        dashboard_status = agent.status
        if agent.status == "initializing":
            dashboard_status = "cold_start"

        return {
            "id": agent.id,
            "name": agent.name,
            "status": dashboard_status,
            "specialty": agent.specialty,
            "description": agent.description,
            "base_model": agent.base_model,
            "model_checkpoint_id": agent.model_checkpoint_id,
            "metrics": metrics,
            "sparkline_data": sparkline,
            "quick_actions": quick_actions,
            "created_at": (
                agent.created_at.isoformat() if agent.created_at else None
            ),
            "updated_at": (
                agent.updated_at.isoformat() if agent.updated_at else None
            ),
            "activated_at": (
                agent.activated_at.isoformat() if agent.activated_at else None
            ),
        }

    # ── Metrics Computation ───────────────────────────────────

    def _compute_metrics(
        self,
        agent: Any,
        db: Session,
    ) -> Dict[str, Any]:
        """Compute headline metrics for an agent.

        Pulls metrics from ticket assignments where the agent was
        involved. Falls back to zeros when no data is available.

        BC-007: Metrics are only meaningful when the model is active.

        Args:
            agent: Agent ORM object.
            db: Database session.

        Returns:
            Metrics dict matching AgentCardMetrics schema.
        """
        # If agent is not active, return zeroed metrics
        if agent.status not in ("active", "paused"):
            return {
                "resolution_rate": None,
                "csat_avg": None,
                "avg_confidence": None,
                "escalation_rate": None,
                "avg_handling_time": None,
                "tickets_handled_24h": 0,
            }

        try:
            from database.models.tickets import (
                Ticket,
                TicketFeedback,
                TicketAssignment,
            )

            # ── Tickets handled in last 24h ──
            now = datetime.now(timezone.utc)
            since_24h = now - timedelta(hours=24)

            tickets_24h = db.query(func.count(TicketAssignment.id)).join(
                Ticket, Ticket.id == TicketAssignment.ticket_id,
            ).filter(
                TicketAssignment.company_id == self.company_id,
                TicketAssignment.assignee_id == agent.id,
                TicketAssignment.assigned_at >= since_24h,
            ).scalar() or 0

            # ── Resolution rate (last 30 days) ──
            since_30d = now - timedelta(days=30)

            total_assigned = db.query(func.count(TicketAssignment.id)).join(
                Ticket, Ticket.id == TicketAssignment.ticket_id,
            ).filter(
                TicketAssignment.company_id == self.company_id,
                TicketAssignment.assignee_id == agent.id,
                TicketAssignment.assigned_at >= since_30d,
            ).scalar() or 0

            resolved = db.query(func.count(TicketAssignment.id)).join(
                Ticket, Ticket.id == TicketAssignment.ticket_id,
            ).filter(
                TicketAssignment.company_id == self.company_id,
                TicketAssignment.assignee_id == agent.id,
                TicketAssignment.assigned_at >= since_30d,
                Ticket.status.in_(["resolved", "closed"]),
            ).scalar() or 0

            resolution_rate = (
                round(resolved / total_assigned * 100, 1)
                if total_assigned > 0
                else None
            )

            # ── CSAT average ──
            avg_csat = db.query(func.avg(TicketFeedback.rating)).join(
                Ticket, Ticket.id == TicketFeedback.ticket_id,
            ).join(
                TicketAssignment,
                TicketAssignment.ticket_id == Ticket.id,
            ).filter(
                TicketAssignment.company_id == self.company_id,
                TicketAssignment.assignee_id == agent.id,
                TicketFeedback.created_at >= since_30d,
            ).scalar()
            csat_avg = round(float(avg_csat), 2) if avg_csat else None

            # ── Escalation rate ──
            escalated = db.query(func.count(TicketAssignment.id)).join(
                Ticket, Ticket.id == TicketAssignment.ticket_id,
            ).filter(
                TicketAssignment.company_id == self.company_id,
                TicketAssignment.assignee_id == agent.id,
                TicketAssignment.assigned_at >= since_30d,
                Ticket.status.in_(["escalated", "awaiting_human"]),
            ).scalar() or 0

            escalation_rate = (
                round(escalated / total_assigned * 100, 1)
                if total_assigned > 0
                else None
            )

            # ── Avg confidence — from AI metadata on tickets ──
            # Best-effort: look for ai_confidence on tickets assigned to agent
            avg_confidence = self._get_avg_confidence(
                agent.id, db, since_30d,
            )

            # ── Avg handling time (minutes) ──
            avg_handling_time = self._get_avg_handling_time(
                agent.id, db, since_30d,
            )

            return {
                "resolution_rate": resolution_rate,
                "csat_avg": csat_avg,
                "avg_confidence": avg_confidence,
                "escalation_rate": escalation_rate,
                "avg_handling_time": avg_handling_time,
                "tickets_handled_24h": tickets_24h,
            }

        except Exception as exc:
            logger.warning(
                "agent_metrics_compute_error",
                company_id=self.company_id,
                agent_id=agent.id,
                error=str(exc),
            )
            return {
                "resolution_rate": None,
                "csat_avg": None,
                "avg_confidence": None,
                "escalation_rate": None,
                "avg_handling_time": None,
                "tickets_handled_24h": 0,
            }

    def _get_avg_confidence(
        self,
        agent_id: str,
        db: Session,
        since: datetime,
    ) -> Optional[float]:
        """Get average AI confidence for agent's tickets."""
        try:
            from database.models.tickets import Ticket, TicketAssignment

            # Check if Ticket has an ai_confidence column
            ticket_model = Ticket.__table__.columns
            if "ai_confidence" not in ticket_model:
                return None

            avg_conf = db.query(func.avg(Ticket.ai_confidence)).join(
                TicketAssignment,
                TicketAssignment.ticket_id == Ticket.id,
            ).filter(
                TicketAssignment.company_id == self.company_id,
                TicketAssignment.assignee_id == agent_id,
                TicketAssignment.assigned_at >= since,
                Ticket.ai_confidence.isnot(None),
            ).scalar()

            return round(float(avg_conf), 1) if avg_conf else None

        except Exception:
            return None

    def _get_avg_handling_time(
        self,
        agent_id: str,
        db: Session,
        since: datetime,
    ) -> Optional[float]:
        """Get average handling time in minutes for agent's tickets."""
        try:
            from database.models.tickets import Ticket, TicketAssignment

            from sqlalchemy import func as sa_func

            avg_minutes = db.query(
                sa_func.avg(
                    sa_func.extract(
                        'epoch',
                        Ticket.first_response_at
                        - Ticket.created_at)
                    / 60)).join(
                TicketAssignment,
                TicketAssignment.ticket_id == Ticket.id,
            ).filter(
                TicketAssignment.company_id == self.company_id,
                TicketAssignment.assignee_id == agent_id,
                TicketAssignment.assigned_at >= since,
                Ticket.first_response_at.isnot(None),
            ).scalar()

            return round(float(avg_minutes), 1) if avg_minutes else None

        except Exception:
            return None

    # ── Sparkline ─────────────────────────────────────────────

    def _compute_sparkline(
        self,
        agent: Any,
        db: Session,
    ) -> List[float]:
        """Compute 14-day resolution rate sparkline for an agent.

        Args:
            agent: Agent ORM object.
            db: Database session.

        Returns:
            List of 14 float values (one per day, most recent last).
        """
        try:
            from database.models.tickets import (
                Ticket, TicketAssignment,
            )

            now = datetime.now(timezone.utc)
            points: List[float] = []

            for i in range(SPARKLINE_DAYS - 1, -1, -1):
                day_start = now - timedelta(days=i)
                day_end = day_start + timedelta(days=1)

                total = db.query(func.count(TicketAssignment.id)).join(
                    Ticket, Ticket.id == TicketAssignment.ticket_id,
                ).filter(
                    TicketAssignment.company_id == self.company_id,
                    TicketAssignment.assignee_id == agent.id,
                    TicketAssignment.assigned_at >= day_start,
                    TicketAssignment.assigned_at < day_end,
                ).scalar() or 0

                resolved = db.query(func.count(TicketAssignment.id)).join(
                    Ticket, Ticket.id == TicketAssignment.ticket_id,
                ).filter(
                    TicketAssignment.company_id == self.company_id,
                    TicketAssignment.assignee_id == agent.id,
                    TicketAssignment.assigned_at >= day_start,
                    TicketAssignment.assigned_at < day_end,
                    Ticket.status.in_(["resolved", "closed"]),
                ).scalar() or 0

                rate = (resolved / total * 100) if total > 0 else 0.0
                points.append(round(rate, 1))

            return points

        except Exception as exc:
            logger.warning(
                "sparkline_compute_error",
                company_id=self.company_id,
                agent_id=agent.id,
                error=str(exc),
            )
            return [0.0] * SPARKLINE_DAYS

    # ── Quick Actions ─────────────────────────────────────────

    def _compute_quick_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """Compute available quick actions for an agent card.

        Args:
            agent: Agent ORM object.

        Returns:
            List of quick-action dicts.
        """
        actions: List[Dict[str, Any]] = []

        # Pause action
        if agent.status in _PAUSE_ALLOWED_FROM:
            actions.append({
                "action": "pause",
                "allowed": True,
                "reason": None,
            })
        elif agent.status == "paused":
            actions.append({
                "action": "pause",
                "allowed": False,
                "reason": "Agent is already paused",
            })
        else:
            actions.append({
                "action": "pause",
                "allowed": False,
                "reason": f"Cannot pause agent in '{agent.status}' status",
            })

        # Resume action
        if agent.status in _RESUME_ALLOWED_FROM:
            actions.append({
                "action": "resume",
                "allowed": True,
                "reason": None,
            })
        elif agent.status in _PAUSE_ALLOWED_FROM:
            actions.append({
                "action": "resume",
                "allowed": False,
                "reason": "Agent is not paused",
            })
        else:
            actions.append({
                "action": "resume",
                "allowed": False,
                "reason": f"Cannot resume agent in '{agent.status}' status",
            })

        # Retrain action
        # BC-007: Retrain only allowed when agent has a model checkpoint
        can_retrain = bool(agent.model_checkpoint_id) and agent.status in (
            "active", "paused", "error",
        )
        actions.append({
            "action": "retrain",
            "allowed": can_retrain,
            "reason": (
                None if can_retrain
                else "No model checkpoint available or agent not in valid state"
            ),
        })

        # View metrics — always allowed
        actions.append({
            "action": "view_metrics",
            "allowed": True,
            "reason": None,
        })

        return actions

    # ── Socket.io Emission (BC-005) ──────────────────────────

    def _emit_status_change(
        self,
        agent_id: str,
        previous_status: str,
        new_status: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Emit agent:status_changed event via Socket.io.

        BC-005: Event is also stored in event buffer for reconnection.
        Uses fire-and-forget — errors are logged but never propagated.

        Args:
            agent_id: Agent UUID.
            previous_status: Status before the change.
            new_status: Status after the change.
            user_id: User who triggered the change.
        """
        try:
            import asyncio

            payload = {
                "agent_id": agent_id,
                "company_id": self.company_id,
                "previous_status": previous_status,
                "new_status": new_status,
                "changed_by": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Try to get a running event loop; create one if needed
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # If we're already in an async context, use create_task
            # Otherwise, run the coroutine directly
            from app.core.socketio import emit_to_tenant

            if loop.is_running():
                asyncio.ensure_future(
                    emit_to_tenant(
                        company_id=self.company_id,
                        event_type="agent:status_changed",
                        payload=payload,
                    ),
                )
            else:
                loop.run_until_complete(
                    emit_to_tenant(
                        company_id=self.company_id,
                        event_type="agent:status_changed",
                        payload=payload,
                    ),
                )

            logger.info(
                "agent_status_changed_emitted",
                company_id=self.company_id,
                agent_id=agent_id,
                previous_status=previous_status,
                new_status=new_status,
            )

        except Exception as exc:
            # BC-005: Socket.io failure must never break the caller
            logger.warning(
                "agent_status_change_emit_failed",
                company_id=self.company_id,
                agent_id=agent_id,
                error=str(exc),
            )

    # ── Utilities ─────────────────────────────────────────────

    @staticmethod
    def _parse_json(value: Optional[str]) -> Dict[str, Any]:
        """Safely parse a JSON string to dict."""
        if not value:
            return {}
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}


# ══════════════════════════════════════════════════════════════════
# LAZY SERVICE LOADING (BC-008)
# ══════════════════════════════════════════════════════════════════


_SERVICE_CACHE_MAX_SIZE = 1000
_service_cache: OrderedDict[str, AgentDashboardService] = OrderedDict()


def get_agent_dashboard_service(
    company_id: str,
) -> AgentDashboardService:
    """Get or create an AgentDashboardService for a tenant (LRU cache).

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        AgentDashboardService instance.
    """
    if company_id not in _service_cache:
        if len(_service_cache) >= _SERVICE_CACHE_MAX_SIZE:
            _service_cache.popitem(last=False)
        _service_cache[company_id] = AgentDashboardService(company_id)
    else:
        _service_cache.move_to_end(company_id)
    return _service_cache[company_id]


__all__ = [
    "AgentDashboardService",
    "get_agent_dashboard_service",
]
