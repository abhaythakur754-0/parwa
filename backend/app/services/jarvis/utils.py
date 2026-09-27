"""
Jarvis utils service — extracted from jarvis_service.py

Contains 30 functions related to utils.
"""

from app.services.jarvis._shared import *

def _get_service(
    service_name: str,
    import_path: str,
    attr_name: Optional[str] = None,
) -> Any:
    """Lazy-load and cache a service class or module.

    Args:
        service_name: Unique cache key for this service.
        import_path: Python import path (e.g. 'app.services.pii_scan_service').
        attr_name: Specific class/function to import. Falls back to service_name.

    Returns:
        The imported class/function, or None if import fails.
    """
    if service_name in _service_cache:
        return _service_cache[service_name]
    try:
        module = __import__(import_path, fromlist=[attr_name or service_name])
        svc = getattr(module, attr_name or service_name, None)
        if svc is not None:
            _service_cache[service_name] = svc
        return svc
    except (ImportError, AttributeError):
        return None


def _get_service_module(module_path: str) -> Any:
    """Lazy-load a service module (for module-level functions).

    Args:
        module_path: Python module path (e.g. 'app.services.analytics_service').

    Returns:
        The imported module, or None if import fails.
    """
    return _get_service(module_path, module_path)


def _clear_service_cache() -> None:
    """Clear all cached services (useful for testing)."""
    _service_cache.clear()


def jarvis_get_analytics(
    db: Session,
    company_id: Optional[str] = None,
    session_id: Optional[str] = None,
    since: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get analytics metrics."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.get_metrics(
                company_id=company_id,
                session_id=session_id,
                since=since,
            )
    except Exception:
        pass
    return None


def jarvis_get_funnel_metrics() -> Optional[Dict[str, Any]]:
    """Get funnel conversion metrics."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.get_funnel_metrics()
    except Exception:
        pass
    return None


def jarvis_get_sentiment_metrics(
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get sentiment analysis metrics for a session."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.get_sentiment_metrics(session_id=session_id)
    except Exception:
        pass
    return None


def jarvis_track_event(
    event_type: str,
    event_category: str,
    user_id: str,
    company_id: str = "",
    session_id: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    source: str = "jarvis",
) -> Optional[Dict[str, Any]]:
    """Track an analytics event."""
    try:
        analytics_svc = _get_service_module("app.services.analytics_service")
        if analytics_svc:
            return analytics_svc.track_event(
                event_type=event_type,
                event_category=event_category,
                user_id=user_id,
                company_id=company_id,
                session_id=session_id,
                properties=properties or {},
                source=source,
            )
    except Exception:
        pass
    return None


def jarvis_capture_lead(
    session_id: str,
    user_id: str,
    company_id: Optional[str] = None,
    session_context: Optional[Dict[str, Any]] = None,
    sentiment_data: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Capture or update a sales lead."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            return lead_svc.capture_lead(
                session_id=session_id,
                user_id=user_id,
                company_id=company_id,
                session_context=session_context or {},
                sentiment_data=sentiment_data,
            )
    except Exception:
        pass
    return None


def jarvis_get_lead(
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """Get lead data for a user."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            lead = lead_svc.get_lead(user_id)
            if lead and hasattr(lead, "to_dict"):
                return lead.to_dict()
    except Exception:
        pass
    return None


def jarvis_get_leads(
    status: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Get all leads, optionally filtered by status."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            if status:
                leads = lead_svc.get_leads_by_status(status)
            else:
                leads = lead_svc.get_all_leads()
            if isinstance(leads, list):
                return [
                    l.to_dict() if hasattr(l, "to_dict") else str(l)
                    for l in leads
                ]
    except Exception:
        pass
    return None


def jarvis_get_lead_stats() -> Optional[Dict[str, Any]]:
    """Get lead statistics."""
    try:
        lead_svc = _get_service_module("app.services.lead_service")
        if lead_svc:
            return lead_svc.get_lead_stats()
    except Exception:
        pass
    return None


def jarvis_get_usage(
    company_id: str,
    db: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    """Get current usage statistics for a company."""
    try:
        svc_cls = _get_service(
            "usage_tracking",
            "app.services.usage_tracking_service",
            "UsageTrackingService",
        )
        if svc_cls:
            svc = svc_cls()
            return svc.get_current_usage(company_id)
    except Exception:
        pass
    return None


def jarvis_check_usage_limit(
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Check if a company is approaching its usage limit."""
    try:
        svc_cls = _get_service(
            "usage_tracking",
            "app.services.usage_tracking_service",
            "UsageTrackingService",
        )
        if svc_cls:
            svc = svc_cls()
            return svc.check_approaching_limit(company_id)
    except Exception:
        pass
    return None


def jarvis_get_invoices(
    company_id: str,
    status: Optional[str] = None,
    limit: int = 20,
) -> Optional[List[Dict[str, Any]]]:
    """Get invoice list for a company."""
    try:
        svc_fn = _get_service(
            "invoice_service_getter",
            "app.services.invoice_service",
            "get_invoice_service",
        )
        if svc_fn:
            svc = svc_fn()
            invoices = svc.get_invoice_list(company_id, status=status, limit=limit)
            if isinstance(invoices, list):
                return [
                    inv.to_dict() if hasattr(inv, "to_dict") else str(inv)
                    for inv in invoices
                ]
    except Exception:
        pass
    return None


def jarvis_get_invoice(
    company_id: str,
    invoice_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a specific invoice."""
    try:
        svc_fn = _get_service(
            "invoice_service_getter",
            "app.services.invoice_service",
            "get_invoice_service",
        )
        if svc_fn:
            svc = svc_fn()
            invoice = svc.get_invoice(company_id, invoice_id)
            if invoice and hasattr(invoice, "to_dict"):
                return invoice.to_dict()
    except Exception:
        pass
    return None


def jarvis_get_monthly_cost_report(
    db: Session,
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Get monthly cost/budget report."""
    try:
        svc_cls = _get_service(
            "cost_protection",
            "app.services.cost_protection_service",
            "CostProtectionService",
        )
        if svc_cls:
            svc = svc_cls(db)
            return svc.get_monthly_report(company_id)
    except Exception:
        pass
    return None


def jarvis_get_audit_trail(
    db: Session,
    company_id: str,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> Optional[List[Dict[str, Any]]]:
    """Query audit trail entries."""
    try:
        audit_svc = _get_service_module("app.services.audit_service")
        if audit_svc:
            entries = audit_svc.query_audit_trail(
                db=db,
                company_id=company_id,
                actor_type=actor_type,
                action=action,
                offset=offset,
                limit=limit,
            )
            if isinstance(entries, list):
                return [
                    e.to_dict() if hasattr(e, "to_dict") else str(e)
                    for e in entries
                ]
    except Exception:
        pass
    return None


def jarvis_get_audit_stats(
    db: Session,
    company_id: str,
    days: int = 30,
) -> Optional[Dict[str, Any]]:
    """Get audit statistics."""
    try:
        audit_svc = _get_service_module("app.services.audit_service")
        if audit_svc:
            return audit_svc.get_audit_stats(db=db, company_id=company_id, days=days)
    except Exception:
        pass
    return None


def jarvis_get_audit_log_events(
    company_id: str,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> Optional[List[Dict[str, Any]]]:
    """Query structured audit log events via AuditLogService."""
    try:
        svc_cls = _get_service(
            "audit_log_service",
            "app.services.audit_log_service",
            "AuditLogService",
        )
        if svc_cls:
            svc = svc_cls(config=None)
            events = svc.query_events(
                company_id=company_id,
                category=category,
                severity=severity,
                limit=limit,
            )
            if isinstance(events, list):
                return [
                    e.to_dict() if hasattr(e, "to_dict") else str(e)
                    for e in events
                ]
    except Exception:
        pass
    return None


def jarvis_get_audit_log_stats(
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Get audit log statistics."""
    try:
        svc_cls = _get_service(
            "audit_log_service",
            "app.services.audit_log_service",
            "AuditLogService",
        )
        if svc_cls:
            svc = svc_cls(config=None)
            stats = svc.get_statistics(company_id=company_id)
            if hasattr(stats, "to_dict"):
                return stats.to_dict()
            return stats
    except Exception:
        pass
    return None


def jarvis_check_rate_limit(
    redis_client: Any = None,
    key: str = "global",
    category: str = "default",
) -> Optional[Dict[str, Any]]:
    """Check rate limit status."""
    try:
        svc_cls = _get_service(
            "rate_limit_service",
            "app.services.rate_limit_service",
            "RateLimitService",
        )
        if svc_cls:
            svc = svc_cls(redis_client=redis_client)
            result = svc.check_rate_limit(key=key, category=category)
            if hasattr(result, "to_headers"):
                return {
                    "allowed": result.allowed,
                    "remaining": result.remaining,
                    "limit": result.limit,
                    "reset_at": str(result.reset_at) if result.reset_at else None,
                }
            return {"allowed": bool(result)}
    except Exception:
        pass
    return None


def jarvis_send_notification(
    db: Session,
    company_id: str,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
) -> Optional[Dict[str, Any]]:
    """Send a notification to a user."""
    try:
        svc_cls = _get_service(
            "notification_service",
            "app.services.notification_service",
            "NotificationService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            return svc.send_notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
            )
    except Exception:
        pass
    return None


def jarvis_send_email(
    to: str,
    subject: str,
    html_content: str,
) -> Optional[Dict[str, Any]]:
    """Send an email via email_service."""
    try:
        email_svc = _get_service_module("app.services.email_service")
        if email_svc:
            email_svc.send_email(
                to=to, subject=subject, html_content=html_content,
            )
            return {"sent": True, "to": to}
    except Exception:
        pass
    return {"sent": False, "error": "email_service_unavailable"}


def jarvis_process_webhook(
    company_id: str,
    provider: str,
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Process an incoming webhook event."""
    try:
        webhook_svc = _get_service_module("app.services.webhook_service")
        if webhook_svc:
            return webhook_svc.process_webhook(
                company_id=company_id,
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
            )
    except Exception:
        pass
    return None


def jarvis_create_customer(
    db: Session,
    company_id: str,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a customer record."""
    try:
        svc_cls = _get_service(
            "customer_service",
            "app.services.customer_service",
            "CustomerService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            customer = svc.create_customer(
                name=name, email=email, phone=phone,
            )
            if customer and hasattr(customer, "to_dict"):
                return customer.to_dict()
            return {"id": str(customer.id), "name": name}
    except Exception:
        pass
    return None


def jarvis_get_customer(
    db: Session,
    company_id: str,
    customer_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a customer by ID."""
    try:
        svc_cls = _get_service(
            "customer_service",
            "app.services.customer_service",
            "CustomerService",
        )
        if svc_cls:
            svc = svc_cls(db, company_id)
            customer = svc.get_customer(customer_id)
            if customer and hasattr(customer, "to_dict"):
                return customer.to_dict()
    except Exception:
        pass
    return None


def jarvis_get_company_profile(
    db: Session,
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """Get company profile settings."""
    try:
        company_svc = _get_service_module("app.services.company_service")
        if company_svc:
            return company_svc.get_company_profile(company_id, db)
    except Exception:
        pass
    return None


def jarvis_update_company_profile(
    db: Session,
    company_id: str,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update company profile settings."""
    try:
        company_svc = _get_service_module("app.services.company_service")
        if company_svc:
            return company_svc.update_company_profile(company_id, data, db)
    except Exception:
        pass
    return None


def jarvis_scan_pii(
    db: Session,
    company_id: str,
    text: str,
    scan_types: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Scan text for PII via pii_scan_service."""
    try:
        svc_cls = _get_service(
            "pii_scan",
            "app.services.pii_scan_service",
            "PIIScanService",
        )
        if svc_cls:
            scanner = svc_cls(db, company_id)
            return scanner.scan_text(text, scan_types=scan_types)
    except Exception:
        pass
    return None


def jarvis_merge_with_brand_voice(
    db: Session,
    company_id: str,
    response_text: str,
) -> Optional[str]:
    """Merge response text with brand voice configuration."""
    try:
        svc_cls = _get_service(
            "brand_voice",
            "app.services.brand_voice_service",
            "BrandVoiceService",
        )
        if svc_cls:
            svc = svc_cls(db)
            return svc.merge_with_brand_voice(response_text, company_id)
    except Exception:
        pass
    return response_text


