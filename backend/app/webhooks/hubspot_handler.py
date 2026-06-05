"""
PARWA HubSpot Webhook Handler

Handles incoming webhook events from HubSpot CRM.
Supports contact, deal, and company lifecycle events.

HubSpot V3 webhooks send batches of event objects. Each event contains:
- eventId, subscriptionId, portalId, appId
- occurredAt, subscriptionType, attemptNumber
- objectId, changeSource, changeFlag

BC-003: HMAC-SHA256 signature verification for all webhooks.
BC-008: Never crash — all event processing wrapped in try/except.
BC-001: All events scoped to company_id via portalId mapping.

Supported event types (7):
- contact.created: New contact created in HubSpot
- contact.updated: Contact properties updated
- contact.deleted: Contact deleted
- deal.created: New deal created
- deal.updated: Deal properties/stage updated
- company.created: New company created
- company.updated: Company properties updated
"""

import logging
from typing import Optional

from app.webhooks import register_handler

logger = logging.getLogger("parwa.webhooks.hubspot")

# Required fields per HubSpot event type
# HubSpot V3 webhooks carry minimal data — objectId is always required.
# Additional required fields depend on the event type.
REQUIRED_FIELDS = {
    "contact.created": ["object_id", "portal_id"],
    "contact.updated": ["object_id", "portal_id"],
    "contact.deleted": ["object_id", "portal_id"],
    "deal.created": ["object_id", "portal_id"],
    "deal.updated": ["object_id", "portal_id"],
    "company.created": ["object_id", "portal_id"],
    "company.updated": ["object_id", "portal_id"],
}


# ── Helpers ─────────────────────────────────────────────────────────


def _sanitize_field(value: str, max_length: int = 255) -> str:
    """Sanitize HubSpot field value.

    Strips control characters and truncates.
    """
    if not value:
        return ""
    cleaned = "".join(
        c for c in str(value) if ord(c) >= 32 or c in "\n\r\t"
    )
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned.strip()


def _validate_required_fields(
    event_type: str, data: dict,
) -> Optional[str]:
    """Validate that required fields exist in extracted data.

    Returns:
        Error message if validation fails, None if OK.
    """
    required = REQUIRED_FIELDS.get(event_type, [])
    for field in required:
        val = data.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            return f"Missing required field: {field}"
    return None


# ── Data Extraction Helpers ──────────────────────────────────────────


def _extract_contact_data(payload: dict) -> dict:
    """Extract and normalize contact data from HubSpot webhook payload.

    HubSpot V3 webhook events contain minimal data:
    - objectId: HubSpot contact ID
    - portalId: HubSpot account (portal) ID
    - changeSource: What triggered the change (CRM, API, etc.)
    - changeFlag: Type of change (NEW, CHANGED, DELETED)

    Full contact data (email, name, etc.) must be fetched via the
    HubSpot CRM API. The webhook handler extracts what is available
    so the service layer can decide whether to enrich.
    """
    properties = payload.get("properties", {}) or {}

    return {
        "object_id": str(payload.get("objectId", "")),
        "portal_id": str(payload.get("portalId", "")),
        "event_id": str(payload.get("eventId", "")),
        "subscription_id": str(payload.get("subscriptionId", "")),
        "app_id": str(payload.get("appId", "")),
        "occurred_at": payload.get("occurredAt"),
        "change_source": _sanitize_field(payload.get("changeSource", ""), 50),
        "change_flag": _sanitize_field(payload.get("changeFlag", ""), 30),
        # Properties may be present in some webhook configurations
        "email": _sanitize_field(properties.get("email", ""), 254),
        "firstname": _sanitize_field(properties.get("firstname", ""), 100),
        "lastname": _sanitize_field(properties.get("lastname", ""), 100),
        "phone": _sanitize_field(properties.get("phone", ""), 30),
        "company": _sanitize_field(properties.get("company", ""), 200),
        "jobtitle": _sanitize_field(properties.get("jobtitle", ""), 100),
        "lifecycle_stage": _sanitize_field(
            properties.get("lifecyclestage", ""), 50
        ),
    }


def _extract_deal_data(payload: dict) -> dict:
    """Extract and normalize deal data from HubSpot webhook payload.

    HubSpot V3 webhook events for deals contain minimal data.
    Full deal properties (dealname, amount, dealstage, pipeline)
    must be fetched via the HubSpot CRM API.
    """
    properties = payload.get("properties", {}) or {}

    return {
        "object_id": str(payload.get("objectId", "")),
        "portal_id": str(payload.get("portalId", "")),
        "event_id": str(payload.get("eventId", "")),
        "subscription_id": str(payload.get("subscriptionId", "")),
        "app_id": str(payload.get("appId", "")),
        "occurred_at": payload.get("occurredAt"),
        "change_source": _sanitize_field(payload.get("changeSource", ""), 50),
        "change_flag": _sanitize_field(payload.get("changeFlag", ""), 30),
        # Properties may be present in some webhook configurations
        "dealname": _sanitize_field(properties.get("dealname", ""), 500),
        "amount": str(properties.get("amount", "")),
        "dealstage": _sanitize_field(properties.get("dealstage", ""), 100),
        "pipeline": _sanitize_field(properties.get("pipeline", ""), 100),
        "closedate": properties.get("closedate"),
        "deal_type": _sanitize_field(
            properties.get("dealtype", ""), 50
        ),
    }


def _extract_company_data(payload: dict) -> dict:
    """Extract and normalize company data from HubSpot webhook payload.

    HubSpot V3 webhook events for companies contain minimal data.
    Full company properties (name, domain, industry) must be
    fetched via the HubSpot CRM API.
    """
    properties = payload.get("properties", {}) or {}

    return {
        "object_id": str(payload.get("objectId", "")),
        "portal_id": str(payload.get("portalId", "")),
        "event_id": str(payload.get("eventId", "")),
        "subscription_id": str(payload.get("subscriptionId", "")),
        "app_id": str(payload.get("appId", "")),
        "occurred_at": payload.get("occurredAt"),
        "change_source": _sanitize_field(payload.get("changeSource", ""), 50),
        "change_flag": _sanitize_field(payload.get("changeFlag", ""), 30),
        # Properties may be present in some webhook configurations
        "name": _sanitize_field(properties.get("name", ""), 500),
        "domain": _sanitize_field(properties.get("domain", ""), 254),
        "industry": _sanitize_field(properties.get("industry", ""), 100),
        "city": _sanitize_field(properties.get("city", ""), 100),
        "state": _sanitize_field(properties.get("state", ""), 100),
        "country": _sanitize_field(properties.get("country", ""), 100),
        "phone": _sanitize_field(properties.get("phone", ""), 30),
        "website": _sanitize_field(properties.get("website", ""), 2000),
    }


# ── Event Handlers ──────────────────────────────────────────────────


def handle_contact_created(event: dict) -> dict:
    """Handle HubSpot contact.created event.

    Triggered when a new contact is created in HubSpot CRM.
    The service layer should enrich by fetching full contact details
    from the HubSpot API using the object_id.

    Args:
        event: Full event dict with keys:
            - event_type: "contact.created"
            - payload: Raw HubSpot webhook event object
            - company_id: Tenant company ID (mapped from portalId)
            - event_id: Provider event ID

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken.
    """
    payload = event.get("payload", {})
    contact_data = _extract_contact_data(payload)

    error = _validate_required_fields("contact.created", contact_data)
    if error:
        return {
            "success": False,
            "event_type": "contact.created",
            "object_id": contact_data.get("object_id", ""),
            "company_id": event.get("company_id"),
            "data": contact_data,
            "action_taken": "validation_failed",
            "error": error,
        }

    logger.info(
        "hubspot_contact_created object_id=%s portal_id=%s source=%s",
        contact_data["object_id"],
        contact_data["portal_id"],
        contact_data.get("change_source", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "success": True,
        "event_type": "contact.created",
        "object_id": contact_data["object_id"],
        "company_id": event.get("company_id"),
        "data": contact_data,
        "action_taken": "contact_created",
    }


def handle_contact_updated(event: dict) -> dict:
    """Handle HubSpot contact.updated event.

    Triggered when a contact's properties are updated in HubSpot CRM.
    Important for syncing contact changes back to PARWA.

    Args:
        event: Full event dict with event_type "contact.updated".

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken.
    """
    payload = event.get("payload", {})
    contact_data = _extract_contact_data(payload)

    error = _validate_required_fields("contact.updated", contact_data)
    if error:
        return {
            "success": False,
            "event_type": "contact.updated",
            "object_id": contact_data.get("object_id", ""),
            "company_id": event.get("company_id"),
            "data": contact_data,
            "action_taken": "validation_failed",
            "error": error,
        }

    logger.info(
        "hubspot_contact_updated object_id=%s portal_id=%s change_flag=%s",
        contact_data["object_id"],
        contact_data["portal_id"],
        contact_data.get("change_flag", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "success": True,
        "event_type": "contact.updated",
        "object_id": contact_data["object_id"],
        "company_id": event.get("company_id"),
        "data": contact_data,
        "action_taken": "contact_updated",
    }


def handle_contact_deleted(event: dict) -> dict:
    """Handle HubSpot contact.deleted event.

    Triggered when a contact is deleted (archived) in HubSpot CRM.
    Critical for data consistency — PARWA should mark the corresponding
    contact as deleted rather than removing it entirely.

    Args:
        event: Full event dict with event_type "contact.deleted".

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken.
    """
    payload = event.get("payload", {})
    contact_data = _extract_contact_data(payload)

    error = _validate_required_fields("contact.deleted", contact_data)
    if error:
        return {
            "success": False,
            "event_type": "contact.deleted",
            "object_id": contact_data.get("object_id", ""),
            "company_id": event.get("company_id"),
            "data": contact_data,
            "action_taken": "validation_failed",
            "error": error,
        }

    logger.info(
        "hubspot_contact_deleted object_id=%s portal_id=%s",
        contact_data["object_id"],
        contact_data["portal_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "success": True,
        "event_type": "contact.deleted",
        "object_id": contact_data["object_id"],
        "company_id": event.get("company_id"),
        "data": contact_data,
        "action_taken": "contact_deleted",
    }


def handle_deal_created(event: dict) -> dict:
    """Handle HubSpot deal.created event.

    Triggered when a new deal is created in HubSpot CRM.
    The service layer should enrich by fetching full deal details
    from the HubSpot API using the object_id.

    Args:
        event: Full event dict with event_type "deal.created".

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken.
    """
    payload = event.get("payload", {})
    deal_data = _extract_deal_data(payload)

    error = _validate_required_fields("deal.created", deal_data)
    if error:
        return {
            "success": False,
            "event_type": "deal.created",
            "object_id": deal_data.get("object_id", ""),
            "company_id": event.get("company_id"),
            "data": deal_data,
            "action_taken": "validation_failed",
            "error": error,
        }

    logger.info(
        "hubspot_deal_created object_id=%s portal_id=%s source=%s",
        deal_data["object_id"],
        deal_data["portal_id"],
        deal_data.get("change_source", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "success": True,
        "event_type": "deal.created",
        "object_id": deal_data["object_id"],
        "company_id": event.get("company_id"),
        "data": deal_data,
        "action_taken": "deal_created",
    }


def handle_deal_updated(event: dict) -> dict:
    """Handle HubSpot deal.updated event.

    Triggered when a deal's properties or stage change in HubSpot CRM.
    Important for tracking deal pipeline progression and stage changes.

    Args:
        event: Full event dict with event_type "deal.updated".

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken.
    """
    payload = event.get("payload", {})
    deal_data = _extract_deal_data(payload)

    error = _validate_required_fields("deal.updated", deal_data)
    if error:
        return {
            "success": False,
            "event_type": "deal.updated",
            "object_id": deal_data.get("object_id", ""),
            "company_id": event.get("company_id"),
            "data": deal_data,
            "action_taken": "validation_failed",
            "error": error,
        }

    logger.info(
        "hubspot_deal_updated object_id=%s portal_id=%s change_flag=%s",
        deal_data["object_id"],
        deal_data["portal_id"],
        deal_data.get("change_flag", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "success": True,
        "event_type": "deal.updated",
        "object_id": deal_data["object_id"],
        "company_id": event.get("company_id"),
        "data": deal_data,
        "action_taken": "deal_updated",
    }


def handle_company_created(event: dict) -> dict:
    """Handle HubSpot company.created event.

    Triggered when a new company is created in HubSpot CRM.
    The service layer should enrich by fetching full company details
    from the HubSpot API using the object_id.

    Args:
        event: Full event dict with event_type "company.created".

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken.
    """
    payload = event.get("payload", {})
    company_data = _extract_company_data(payload)

    error = _validate_required_fields("company.created", company_data)
    if error:
        return {
            "success": False,
            "event_type": "company.created",
            "object_id": company_data.get("object_id", ""),
            "company_id": event.get("company_id"),
            "data": company_data,
            "action_taken": "validation_failed",
            "error": error,
        }

    logger.info(
        "hubspot_company_created object_id=%s portal_id=%s source=%s",
        company_data["object_id"],
        company_data["portal_id"],
        company_data.get("change_source", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "success": True,
        "event_type": "company.created",
        "object_id": company_data["object_id"],
        "company_id": event.get("company_id"),
        "data": company_data,
        "action_taken": "company_created",
    }


def handle_company_updated(event: dict) -> dict:
    """Handle HubSpot company.updated event.

    Triggered when a company's properties are updated in HubSpot CRM.
    Important for syncing company data changes back to PARWA.

    Args:
        event: Full event dict with event_type "company.updated".

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken.
    """
    payload = event.get("payload", {})
    company_data = _extract_company_data(payload)

    error = _validate_required_fields("company.updated", company_data)
    if error:
        return {
            "success": False,
            "event_type": "company.updated",
            "object_id": company_data.get("object_id", ""),
            "company_id": event.get("company_id"),
            "data": company_data,
            "action_taken": "validation_failed",
            "error": error,
        }

    logger.info(
        "hubspot_company_updated object_id=%s portal_id=%s change_flag=%s",
        company_data["object_id"],
        company_data["portal_id"],
        company_data.get("change_flag", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "success": True,
        "event_type": "company.updated",
        "object_id": company_data["object_id"],
        "company_id": event.get("company_id"),
        "data": company_data,
        "action_taken": "company_updated",
    }


# ── Event Type Registry ─────────────────────────────────────────────

# Event type to handler mapping (PROVIDER_EVENT_TYPES pattern)
_HUBSPOT_HANDLERS = {
    "contact.created": handle_contact_created,
    "contact.updated": handle_contact_updated,
    "contact.deleted": handle_contact_deleted,
    "deal.created": handle_deal_created,
    "deal.updated": handle_deal_updated,
    "company.created": handle_company_created,
    "company.updated": handle_company_updated,
}


# ── Main Dispatcher ─────────────────────────────────────────────────


@register_handler("hubspot")
def handle_hubspot_event(event: dict) -> dict:
    """Main HubSpot webhook handler dispatcher.

    Routes to the correct sub-handler based on event_type.
    Supports 7 event types:
    - contact.created, contact.updated, contact.deleted
    - deal.created, deal.updated
    - company.created, company.updated

    HubSpot V3 webhooks send batches — the caller should iterate
    over the batch and call this dispatcher once per event.

    BC-008: Never crash — all handler errors are caught and returned
    as error result dicts instead of propagating exceptions.

    Args:
        event: Full event dict with keys:
            - event_type: HubSpot subscription type (e.g., "contact.created")
            - payload: Raw HubSpot webhook event object
            - company_id: Tenant company ID (mapped from portalId)
            - event_id: Provider event ID

    Returns:
        Dict with success, event_type, object_id, company_id, data,
        and action_taken. On handler error, success=False with error msg.
    """
    event_type = event.get("event_type", "")

    handler = _HUBSPOT_HANDLERS.get(event_type)
    if not handler:
        logger.warning(
            "hubspot_unknown_event_type type=%s event_id=%s",
            event_type,
            event.get("event_id"),
            extra={"company_id": event.get("company_id")},
        )
        return {
            "success": False,
            "event_type": event_type,
            "object_id": str(event.get("payload", {}).get("objectId", "")),
            "company_id": event.get("company_id"),
            "data": {},
            "action_taken": "unknown_event_type",
            "error": f"Unknown HubSpot event type: {event_type}",
            "supported_types": list(_HUBSPOT_HANDLERS.keys()),
        }

    try:
        return handler(event)
    except Exception as exc:
        logger.error(
            "hubspot_handler_error type=%s error=%s",
            event_type, str(exc)[:200],
            extra={
                "company_id": event.get("company_id"),
                "event_id": event.get("event_id"),
            },
        )
        return {
            "success": False,
            "event_type": event_type,
            "object_id": str(event.get("payload", {}).get("objectId", "")),
            "company_id": event.get("company_id"),
            "data": {},
            "action_taken": "handler_error",
            "error": f"Handler error for {event_type}: {str(exc)[:200]}",
        }
