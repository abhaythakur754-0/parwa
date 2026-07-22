"""
Jarvis tickets service — extracted from jarvis_service.py

Contains 34 functions related to tickets.
"""

from app.services.jarvis._shared import *

def create_action_ticket(
    db: Session,
    session_id: str,
    user_id: str,
    ticket_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> JarvisActionTicket:
    """Create an action ticket for a user action."""
    get_session(db, session_id, user_id)  # Auth check

    return _create_ticket(db, session_id, ticket_type, metadata or {})


def _create_ticket(
    db: Session,
    session_id: str,
    ticket_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> JarvisActionTicket:
    """Internal: create ticket without auth check."""
    ticket = JarvisActionTicket(
        session_id=session_id,
        ticket_type=ticket_type,
        status="pending",
        metadata_json=json.dumps(metadata or {}),
        result_json="{}",
    )
    db.add(ticket)
    db.flush()
    return ticket


def get_tickets(
    db: Session,
    session_id: str,
    user_id: str,
) -> List[JarvisActionTicket]:
    """Get all action tickets for a session."""
    get_session(db, session_id, user_id)  # Auth check
    return (
        db.query(JarvisActionTicket)
        .filter(JarvisActionTicket.session_id == session_id)
        .order_by(JarvisActionTicket.created_at.desc())
        .all()
    )


def get_ticket(
    db: Session,
    ticket_id: str,
    user_id: str,
) -> JarvisActionTicket:
    """Get a single action ticket with result."""
    ticket = (
        db.query(JarvisActionTicket)
        .filter(JarvisActionTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise NotFoundError(
            message="Ticket not found",
            details={"ticket_id": ticket_id},
        )
    # Verify user owns the session
    get_session(db, ticket.session_id, user_id)
    return ticket


def update_ticket_status(
    db: Session,
    ticket_id: str,
    user_id: str,
    status: str,
) -> JarvisActionTicket:
    """Update ticket status."""
    ticket = get_ticket(db, ticket_id, user_id)
    ticket.status = status
    ticket.updated_at = datetime.now(timezone.utc)

    if status == "completed":
        ticket.completed_at = datetime.now(timezone.utc)

    db.flush()
    return ticket


def complete_ticket(
    db: Session,
    ticket_id: str,
    user_id: str,
    result_data: Dict[str, Any],
) -> JarvisActionTicket:
    """Mark ticket completed with result data."""
    ticket = get_ticket(db, ticket_id, user_id)
    ticket.status = "completed"
    ticket.result_json = json.dumps(result_data)
    ticket.completed_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    db.flush()
    return ticket


def _complete_latest_ticket(
    db: Session,
    session_id: str,
    ticket_type: str,
    result_data: Dict[str, Any],
) -> Optional[JarvisActionTicket]:
    """Internal: complete the latest pending ticket of a given type."""
    ticket = (
        db.query(JarvisActionTicket)
        .filter(
            JarvisActionTicket.session_id == session_id,
            JarvisActionTicket.ticket_type == ticket_type,
            JarvisActionTicket.status == "pending",
        )
        .order_by(JarvisActionTicket.created_at.desc())
        .first()
    )
    if ticket:
        ticket.status = "completed"
        ticket.result_json = json.dumps(result_data)
        ticket.completed_at = datetime.now(timezone.utc)
        ticket.updated_at = datetime.now(timezone.utc)
        db.flush()
    return ticket


def jarvis_create_ticket(
    db: Session,
    company_id: str,
    subject: str,
    description: str,
    customer_id: Optional[str] = None,
    priority: str = "medium",
    category: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a customer care ticket via ticket_service.

    Args:
        db: Database session.
        company_id: Company owning the ticket.
        subject: Ticket subject/title.
        description: Ticket description/body.
        customer_id: Optional customer identifier.
        priority: Ticket priority (low/medium/high/urgent).
        category: Optional ticket category.

    Returns:
        Created ticket data dict, or None if service unavailable.
    """
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.create_ticket(
                subject=subject,
                description=description,
                customer_id=customer_id,
                priority=priority,
                category=category,
            )
            if hasattr(ticket, "to_dict"):
                return ticket.to_dict()
            return {"id": str(ticket.id), "subject": subject}
    except Exception:
        pass
    return None


def jarvis_get_tickets(
    db: Session,
    company_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Optional[List[Dict[str, Any]]]:
    """List tickets for a company via ticket_service."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            tickets = svc.list_tickets(status=status, limit=limit, offset=offset)
            if isinstance(tickets, list):
                return [
                    t.to_dict() if hasattr(t, "to_dict") else str(t)
                    for t in tickets
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a single ticket by ID."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.get_ticket(ticket_id)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
            return {"id": ticket_id} if ticket else None
    except Exception:
        pass
    return None


def jarvis_update_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update a ticket's fields."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.update_ticket(ticket_id, **updates)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
    except Exception:
        pass
    return None


def jarvis_delete_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Delete a ticket."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.delete_ticket(ticket_id)
            return {"deleted": True, "ticket_id": ticket_id}
    except Exception:
        pass
    return None


def jarvis_assign_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
    assignee_id: str,
) -> Optional[Dict[str, Any]]:
    """Assign a ticket to an agent/user."""
    try:
        svc_cls = _get_service(
            "ticket_service",
            "app.services.ticket_service",
            "TicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc.assign_ticket(ticket_id, assignee_id)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
    except Exception:
        pass
    return None


def jarvis_transition_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
    target_state: str,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Transition a ticket state via state machine."""
    try:
        sm_cls = _get_service(
            "ticket_state_machine",
            "app.services.ticket_state_machine",
            "TicketStateMachine",
        )
        if sm_cls:
            sm = sm_cls(db, company_id)
            ticket = sm.transition(ticket_id, target_state, reason=reason)
            if ticket and hasattr(ticket, "to_dict"):
                return ticket.to_dict()
            return {"ticket_id": ticket_id, "new_state": target_state}
    except Exception:
        pass
    return None


def jarvis_classify_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Classify a ticket's intent and urgency."""
    try:
        svc_cls = _get_service(
            "classification_service",
            "app.services.classification_service",
            "ClassificationService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.classify(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "classification": str(result)}
    except Exception:
        pass
    return None


def jarvis_search_tickets(
    db: Session,
    company_id: str,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 20,
) -> Optional[List[Dict[str, Any]]]:
    """Search tickets via ticket_search_service."""
    try:
        svc_cls = _get_service(
            "ticket_search_service",
            "app.services.ticket_search_service",
            "TicketSearchService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            results = svc.search(query, filters=filters, limit=limit)
            if isinstance(results, list):
                return [
                    r.to_dict() if hasattr(r, "to_dict") else str(r)
                    for r in results
                ]
    except Exception:
        pass
    return None


def jarvis_merge_tickets(
    db: Session,
    company_id: str,
    primary_ticket_id: str,
    secondary_ticket_ids: List[str],
) -> Optional[Dict[str, Any]]:
    """Merge multiple tickets into one via ticket_merge_service."""
    try:
        svc_cls = _get_service(
            "ticket_merge_service",
            "app.services.ticket_merge_service",
            "TicketMergeService",
        )
        if svc_cls:
            svc = svc_cls(db)
            result = svc.merge_tickets(
                primary_ticket_id, secondary_ticket_ids, company_id,
            )
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"merged": True, "primary": primary_ticket_id}
    except Exception:
        pass
    return None


def jarvis_check_ticket_lifecycle(
    db: Session,
    company_id: str,
    ticket_id: str,
    check_type: str = "duplicate",
) -> Optional[Dict[str, Any]]:
    """Run lifecycle checks (duplicate, out-of-scope, etc.)."""
    try:
        svc_cls = _get_service(
            "ticket_lifecycle_service",
            "app.services.ticket_lifecycle_service",
            "TicketLifecycleService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            if check_type == "duplicate":
                result = svc.check_duplicate(ticket_id)
            elif check_type == "out_of_scope":
                result = svc.check_out_of_plan_scope(ticket_id)
            elif check_type == "ai_cant_solve":
                result = svc.handle_ai_cant_solve(ticket_id)
            elif check_type == "human_request":
                result = svc.handle_human_request(ticket_id)
            else:
                result = svc.check_duplicate(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "check": check_type}
    except Exception:
        pass
    return None


def jarvis_get_ticket_analytics(
    db: Session,
    company_id: str,
    days: int = 30,
) -> Optional[Dict[str, Any]]:
    """Get ticket analytics summary."""
    try:
        svc_cls = _get_service(
            "ticket_analytics_service",
            "app.services.ticket_analytics_service",
            "TicketAnalyticsService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            summary = svc.get_summary(days=days)
            trends = svc.get_trends(days=days)
            result = {}
            if hasattr(summary, "to_dict"):
                result["summary"] = summary.to_dict()
            if hasattr(trends, "__iter__"):
                result["trends"] = [
                    t.to_dict() if hasattr(t, "to_dict") else str(t)
                    for t in trends
                ]
            return result
    except Exception:
        pass
    return None


def jarvis_detect_stale_tickets(
    db: Session,
    company_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Detect stale tickets that need attention."""
    try:
        svc_cls = _get_service(
            "stale_ticket_service",
            "app.services.stale_ticket_service",
            "StaleTicketService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            stale = svc.detect_stale_tickets()
            if isinstance(stale, list):
                return [
                    s.to_dict() if hasattr(s, "to_dict") else str(s)
                    for s in stale
                ]
    except Exception:
        pass
    return None


def jarvis_analyze_spam(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Analyze a ticket for spam."""
    try:
        svc_cls = _get_service(
            "spam_detection_service",
            "app.services.spam_detection_service",
            "SpamDetectionService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.analyze_ticket(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "spam_analysis": str(result)}
    except Exception:
        pass
    return None


def jarvis_auto_tag_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[str]]:
    """Auto-tag a ticket based on content."""
    try:
        svc_cls = _get_service(
            "tag_service",
            "app.services.tag_service",
            "TagService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.auto_tag(ticket_id)
            if isinstance(result, list):
                return result
            if hasattr(result, "tags"):
                return result.tags
    except Exception:
        pass
    return None


def jarvis_detect_category(
    db: Session,
    company_id: str,
    text: str,
) -> Optional[Dict[str, Any]]:
    """Detect ticket category from text."""
    try:
        svc_cls = _get_service(
            "category_service",
            "app.services.category_service",
            "CategoryService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.detect_category(text)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"category": str(result)}
    except Exception:
        pass
    return None


def jarvis_detect_priority(
    db: Session,
    company_id: str,
    text: str,
    customer_tier: str = "standard",
) -> Optional[Dict[str, Any]]:
    """Detect ticket priority from text."""
    try:
        svc_cls = _get_service(
            "priority_service",
            "app.services.priority_service",
            "PriorityService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.detect_priority(text, customer_tier=customer_tier)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"priority": str(result)}
    except Exception:
        pass
    return None


def jarvis_auto_assign_ticket(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Auto-assign a ticket to the best agent."""
    try:
        svc_cls = _get_service(
            "assignment_service",
            "app.services.assignment_service",
            "AssignmentService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            result = svc.auto_assign(ticket_id)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"ticket_id": ticket_id, "assigned": str(result)}
    except Exception:
        pass
    return None


def jarvis_get_sla_target(
    db: Session,
    company_id: str,
    priority: str = "medium",
) -> Optional[Dict[str, Any]]:
    """Get SLA target for a priority level."""
    try:
        svc_cls = _get_service(
            "sla_service",
            "app.services.sla_service",
            "SLAService",
        )
        if svc_cls:
            svc = svc_cls(db)
            result = svc.get_policy_by_tier_priority(
                company_id=company_id, priority=priority,
            )
            if result and hasattr(result, "to_dict"):
                return result.to_dict()
    except Exception:
        pass
    return None


def jarvis_evaluate_triggers(
    db: Session,
    company_id: str,
    ticket_id: str,
    event_type: str = "created",
) -> Optional[List[Dict[str, Any]]]:
    """Evaluate automation triggers for a ticket event."""
    try:
        svc_cls = _get_service(
            "trigger_service",
            "app.services.trigger_service",
            "TriggerService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            results = svc.evaluate_triggers(ticket_id, event_type)
            if isinstance(results, list):
                return [
                    r.to_dict() if hasattr(r, "to_dict") else str(r)
                    for r in results
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket_tags(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[str]]:
    """Get tags for a ticket."""
    try:
        svc_cls = _get_service(
            "tag_service",
            "app.services.tag_service",
            "TagService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            ticket = svc._get_ticket(ticket_id) if hasattr(svc, "_get_ticket") else None
            if ticket and hasattr(ticket, "tags"):
                return ticket.tags
    except Exception:
        pass
    return None


def jarvis_get_ticket_notes(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get internal notes for a ticket."""
    try:
        svc_cls = _get_service(
            "internal_note_service",
            "app.services.internal_note_service",
            "InternalNoteService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            notes = svc.list_notes(ticket_id)
            if isinstance(notes, list):
                return [
                    n.to_dict() if hasattr(n, "to_dict") else str(n)
                    for n in notes
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket_messages(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get messages for a ticket."""
    try:
        svc_cls = _get_service(
            "message_service",
            "app.services.message_service",
            "MessageService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            messages = svc.list_messages(ticket_id)
            if isinstance(messages, list):
                return [
                    m.to_dict() if hasattr(m, "to_dict") else str(m)
                    for m in messages
                ]
    except Exception:
        pass
    return None


def jarvis_get_ticket_attachments(
    db: Session,
    company_id: str,
    ticket_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get attachments for a ticket."""
    try:
        svc_cls = _get_service(
            "attachment_service",
            "app.services.attachment_service",
            "AttachmentService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            attachments = svc.get_attachments(ticket_id)
            if isinstance(attachments, list):
                return [
                    a.to_dict() if hasattr(a, "to_dict") else str(a)
                    for a in attachments
                ]
    except Exception:
        pass
    return None


def jarvis_get_channel_config(
    db: Session,
    company_id: str,
    channel: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get channel configuration."""
    try:
        svc_cls = _get_service(
            "channel_service",
            "app.services.channel_service",
            "ChannelService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            if channel:
                return svc.get_channel_config(channel)
            return svc.get_company_channel_config()
    except Exception:
        pass
    return None


def jarvis_execute_bulk_action(
    db: Session,
    company_id: str,
    action_type: str,
    ticket_ids: List[str],
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Execute a bulk action on multiple tickets."""
    try:
        svc_cls = _get_service(
            "bulk_action_service",
            "app.services.bulk_action_service",
            "BulkActionService",
        )
        if svc_cls:
            svc = svc_cls(db)
            result = svc.execute_bulk_action(
                company_id=company_id,
                action_type=action_type,
                ticket_ids=ticket_ids,
                params=params or {},
            )
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return {"action": action_type, "processed": len(ticket_ids)}
    except Exception:
        pass
    return None


def jarvis_get_channels(
    db: Session,
    company_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Get available channels for a company."""
    try:
        svc_cls = _get_service(
            "channel_service",
            "app.services.channel_service",
            "ChannelService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            channels = svc.get_available_channels()
            if isinstance(channels, list):
                return channels
    except Exception:
        pass
    return None


