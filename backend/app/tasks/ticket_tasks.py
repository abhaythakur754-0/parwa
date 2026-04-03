"""
PARWA Ticket Celery Tasks (Day 28)

Implements ticket-related async tasks:
- classify_ticket: AI classification (stub for Week 9)
- score_assignments: Score-based assignment (stub for Week 9)
- check_duplicate_ticket: PS05 duplicate detection
- index_ticket_for_search: Search index update
- auto_assign_ticket: Async auto-assignment

BC-001: All tasks use company_id for tenant isolation.
BC-004: Tasks use retry with DLQ routing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from celery import shared_task

from backend.app.tasks.base import ParwaTask
from backend.app.tasks.celery_app import app
from database.base import SessionLocal
from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketIntent,
    TicketAssignment,
    AssignmentRule,
    TicketStatus,
    TicketPriority,
)
from database.models.core import User

logger = logging.getLogger(__name__)


# ── CLASSIFICATION TASKS ───────────────────────────────────────────────────

@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.classify_ticket",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
    default_retry_delay=5,
)
def classify_ticket(
    self,
    company_id: str,
    ticket_id: str,
    force_reclassify: bool = False,
) -> Dict[str, Any]:
    """Classify a ticket (Week 4: rule-based, Week 9: AI).

    Args:
        company_id: Company ID for tenant isolation
        ticket_id: Ticket ID to classify
        force_reclassify: Force reclassification even if already classified

    Returns:
        Classification result
    """
    logger.info(
        "Classifying ticket",
        extra={
            "company_id": company_id,
            "ticket_id": ticket_id,
            "force_reclassify": force_reclassify,
        }
    )

    from backend.app.services.classification_service import ClassificationService

    with SessionLocal() as db:
        try:
            service = ClassificationService(db, company_id)
            result = service.classify(ticket_id, force_reclassify)

            logger.info(
                "Ticket classified",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "intent": result.get("intent"),
                    "urgency": result.get("urgency"),
                    "confidence": result.get("confidence"),
                }
            )

            return result

        except Exception as e:
            logger.error(
                "Ticket classification failed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "error": str(e),
                }
            )
            raise self.retry(exc=e)


@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.batch_classify",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def batch_classify(
    self,
    company_id: str,
    ticket_ids: list,
) -> Dict[str, Any]:
    """Classify multiple tickets in batch.

    Args:
        company_id: Company ID
        ticket_ids: List of ticket IDs to classify

    Returns:
        Batch classification result
    """
    logger.info(
        "Batch classifying tickets",
        extra={
            "company_id": company_id,
            "ticket_count": len(ticket_ids),
        }
    )

    success_count = 0
    failure_count = 0
    results = []

    for ticket_id in ticket_ids:
        try:
            result = classify_ticket.apply_async(
                args=[company_id, ticket_id, False],
                queue="ai_light",
            )
            success_count += 1
            results.append({"ticket_id": ticket_id, "status": "queued"})
        except Exception as e:
            failure_count += 1
            results.append({
                "ticket_id": ticket_id,
                "status": "failed",
                "error": str(e),
            })

    return {
        "total": len(ticket_ids),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
    }


# ── ASSIGNMENT TASKS ───────────────────────────────────────────────────────

@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.score_assignments",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
    default_retry_delay=5,
)
def score_assignments(
    self,
    company_id: str,
    ticket_id: str,
) -> Dict[str, Any]:
    """Get assignment scores for a ticket.

    Week 4: Rule-based scoring.
    Week 9: AI-based scoring.

    Args:
        company_id: Company ID
        ticket_id: Ticket ID

    Returns:
        Assignment scores
    """
    logger.info(
        "Scoring assignments for ticket",
        extra={
            "company_id": company_id,
            "ticket_id": ticket_id,
        }
    )

    from backend.app.services.assignment_service import AssignmentService

    with SessionLocal() as db:
        try:
            service = AssignmentService(db, company_id)
            result = service.get_assignment_scores(ticket_id)

            return result

        except Exception as e:
            logger.error(
                "Assignment scoring failed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "error": str(e),
                }
            )
            raise self.retry(exc=e)


@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.auto_assign",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
    default_retry_delay=5,
)
def auto_assign_ticket(
    self,
    company_id: str,
    ticket_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Auto-assign a ticket based on rules.

    Args:
        company_id: Company ID
        ticket_id: Ticket ID
        user_id: User triggering assignment

    Returns:
        Assignment result
    """
    logger.info(
        "Auto-assigning ticket",
        extra={
            "company_id": company_id,
            "ticket_id": ticket_id,
        }
    )

    from backend.app.services.assignment_service import AssignmentService

    with SessionLocal() as db:
        try:
            service = AssignmentService(db, company_id)
            result = service.auto_assign(ticket_id, user_id)

            logger.info(
                "Ticket auto-assigned",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "assignee_id": result.get("assignee_id"),
                    "rule_name": result.get("rule_name"),
                }
            )

            return result

        except Exception as e:
            logger.error(
                "Auto-assignment failed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "error": str(e),
                }
            )
            raise self.retry(exc=e)


@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.auto_assign_new_tickets",
    soft_time_limit=120,
    time_limit=180,
)
def auto_assign_new_tickets(
    self,
    company_id: str,
) -> Dict[str, Any]:
    """Auto-assign all new unassigned tickets.

    Periodic task to assign tickets that were created
    but not yet assigned.

    Args:
        company_id: Company ID

    Returns:
        Summary of assignments
    """
    logger.info(
        "Auto-assigning new tickets",
        extra={"company_id": company_id}
    )

    with SessionLocal() as db:
        # Get unassigned open tickets
        unassigned = db.query(Ticket).filter(
            Ticket.company_id == company_id,
            Ticket.assigned_to == None,
            Ticket.status == TicketStatus.open.value,
        ).all()

        assigned_count = 0
        failed_count = 0

        for ticket in unassigned:
            try:
                # Queue individual assignment task
                auto_assign_ticket.apply_async(
                    args=[company_id, ticket.id],
                    queue="default",
                )
                assigned_count += 1
            except Exception as e:
                logger.error(
                    "Failed to queue assignment",
                    extra={
                        "company_id": company_id,
                        "ticket_id": ticket.id,
                        "error": str(e),
                    }
                )
                failed_count += 1

        return {
            "total_unassigned": len(unassigned),
            "queued_for_assignment": assigned_count,
            "failed": failed_count,
        }


# ── DUPLICATE DETECTION ────────────────────────────────────────────────────

@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.check_duplicate",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
def check_duplicate_ticket(
    self,
    company_id: str,
    ticket_id: str,
) -> Dict[str, Any]:
    """Check for duplicate tickets (PS05).

    Args:
        company_id: Company ID
        ticket_id: Ticket ID to check

    Returns:
        Duplicate check result
    """
    logger.info(
        "Checking for duplicate tickets",
        extra={
            "company_id": company_id,
            "ticket_id": ticket_id,
        }
    )

    from backend.app.services.ticket_search_service import TicketSearchService
    from backend.app.services.ticket_service import TicketService

    with SessionLocal() as db:
        try:
            # Get ticket
            ticket_service = TicketService(db, company_id)
            ticket = ticket_service.get_ticket(ticket_id)

            if not ticket.subject:
                return {
                    "ticket_id": ticket_id,
                    "duplicate_found": False,
                    "reason": "No subject to compare",
                }

            # Search for similar tickets
            search_service = TicketSearchService(db, company_id)
            similar = search_service.search_by_similarity(
                text=ticket.subject,
                threshold=0.85,
                limit=5,
            )

            # Filter out self
            similar = [
                s for s in similar
                if s["ticket"]["id"] != ticket_id
            ]

            if similar:
                logger.info(
                    "Duplicate tickets found",
                    extra={
                        "company_id": company_id,
                        "ticket_id": ticket_id,
                        "duplicate_count": len(similar),
                    }
                )

            return {
                "ticket_id": ticket_id,
                "duplicate_found": len(similar) > 0,
                "similar_tickets": similar[:3],
                "highest_similarity": (
                    similar[0]["similarity"] if similar else 0
                ),
            }

        except Exception as e:
            logger.error(
                "Duplicate check failed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "error": str(e),
                }
            )
            raise self.retry(exc=e)


# ── SEARCH INDEXING ────────────────────────────────────────────────────────

@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.index_for_search",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
def index_ticket_for_search(
    self,
    company_id: str,
    ticket_id: str,
) -> Dict[str, Any]:
    """Index a ticket for search.

    For now, this is a no-op as we use PostgreSQL full-text search.
    In the future, this will populate external search indices (Elasticsearch, etc.)

    Args:
        company_id: Company ID
        ticket_id: Ticket ID

    Returns:
        Index result
    """
    logger.info(
        "Indexing ticket for search",
        extra={
            "company_id": company_id,
            "ticket_id": ticket_id,
        }
    )

    # Placeholder for external search index integration
    # Would update Elasticsearch, Meilisearch, etc.

    return {
        "ticket_id": ticket_id,
        "indexed": True,
        "index_type": "postgresql_fulltext",  # Future: "elasticsearch"
    }


@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.reindex_company",
    soft_time_limit=600,
    time_limit=900,
)
def reindex_company_tickets(
    self,
    company_id: str,
) -> Dict[str, Any]:
    """Reindex all tickets for a company.

    Args:
        company_id: Company ID

    Returns:
        Reindex result
    """
    logger.info(
        "Reindexing company tickets",
        extra={"company_id": company_id}
    )

    with SessionLocal() as db:
        tickets = db.query(Ticket.id).filter(
            Ticket.company_id == company_id,
        ).all()

        indexed_count = 0
        for (ticket_id,) in tickets:
            try:
                index_ticket_for_search.apply_async(
                    args=[company_id, ticket_id],
                    queue="default",
                )
                indexed_count += 1
            except Exception as e:
                logger.error(
                    "Failed to queue reindex",
                    extra={
                        "company_id": company_id,
                        "ticket_id": ticket_id,
                        "error": str(e),
                    }
                )

        return {
            "company_id": company_id,
            "total_tickets": len(tickets),
            "queued_for_indexing": indexed_count,
        }


# ── TICKET LIFECYCLE TASKS ─────────────────────────────────────────────────

@app.task(
    base=ParwaTask,
    bind=True,
    name="ticket.process_new_ticket",
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def process_new_ticket(
    self,
    company_id: str,
    ticket_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Process a newly created ticket.

    Runs classification, duplicate check, and auto-assignment.

    Args:
        company_id: Company ID
        ticket_id: Ticket ID
        user_id: User who created the ticket

    Returns:
        Processing result
    """
    logger.info(
        "Processing new ticket",
        extra={
            "company_id": company_id,
            "ticket_id": ticket_id,
        }
    )

    results = {}

    # 1. Classify ticket
    try:
        classify_result = classify_ticket.apply_async(
            args=[company_id, ticket_id, False],
            queue="ai_light",
        )
        results["classification"] = "queued"
    except Exception as e:
        results["classification"] = f"failed: {str(e)}"

    # 2. Check for duplicates
    try:
        duplicate_result = check_duplicate_ticket.apply_async(
            args=[company_id, ticket_id],
            queue="default",
        )
        results["duplicate_check"] = "queued"
    except Exception as e:
        results["duplicate_check"] = f"failed: {str(e)}"

    # 3. Auto-assign
    try:
        assign_result = auto_assign_ticket.apply_async(
            args=[company_id, ticket_id, user_id],
            queue="default",
        )
        results["assignment"] = "queued"
    except Exception as e:
        results["assignment"] = f"failed: {str(e)}"

    # 4. Index for search
    try:
        index_result = index_ticket_for_search.apply_async(
            args=[company_id, ticket_id],
            queue="default",
        )
        results["search_index"] = "queued"
    except Exception as e:
        results["search_index"] = f"failed: {str(e)}"

    return {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "processing": results,
    }
