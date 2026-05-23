"""
PARWA Activity Capture Middleware

Automatically captures HTTP requests as ActivityLog entries for non-agentic
awareness. This is how the Activity Store gets populated with user actions,
billing events, system events, etc. — WITHOUT any service needing to call
log_activity() manually.

Architecture:
  This middleware runs AFTER the request completes and records:
    - User actions: page views, button clicks (POST to non-api routes)
    - Billing events: any request to /api/v1/billing/*
    - Configuration changes: PUT/PATCH to /api/v1/settings/*
    - System events: webhook deliveries, cron calls
    - Workflow events: ticket create/update/resolve

  It uses route patterns to auto-categorize events, so new routes
  are automatically covered without code changes.

  Routes that are SKIPPED (too noisy):
    - /health, /ready, /metrics
    - GET requests to list endpoints (just browsing)
    - Static assets, favicon, etc.

  Routes that are ALWAYS logged:
    - POST/PUT/PATCH/DELETE to billing endpoints
    - POST to ticket endpoints (creation)
    - PUT/PATCH to configuration endpoints
    - Any request returning 5xx (errors)

BC-001: company_id from tenant middleware.
BC-008: Never crash — all logging is best-effort.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logger import get_logger

logger = get_logger("activity_capture")

# ── Routes to skip (too noisy, no awareness value) ────────────

SKIP_PATHS = {
    "/health", "/ready", "/metrics", "/favicon.ico",
    "/robots.txt", "/sitemap.xml",
}

SKIP_PREFIXES = (
    "/static/", "/assets/", "/_next/", "/__nextjs",
    "/docs", "/openapi.json", "/redoc",
)

# ── Route → Category mapping ──────────────────────────────────

ROUTE_CATEGORY_MAP = {
    "/api/v1/billing": "billing",
    "/api/v1/subscriptions": "billing",
    "/api/v1/payments": "billing",
    "/api/v1/invoices": "billing",
    "/api/v1/pricing": "billing",
    "/api/v1/tickets": "workflow",
    "/api/v1/sla": "configuration",
    "/api/v1/settings": "configuration",
    "/api/v1/integrations": "integration",
    "/api/v1/agents": "configuration",
    "/api/v1/channels": "configuration",
    "/api/v1/email": "channel",
    "/api/v1/sms": "channel",
    "/api/v1/voice": "channel",
    "/api/v1/chat": "channel",
    "/api/v1/ai": "system",
    "/api/v1/jarvis": "system",
    "/api/v1/analytics": "system",
    "/api/v1/notifications": "notification",
    "/api/v1/users": "configuration",
    "/api/v1/onboarding": "workflow",
    "/api/v1/webhooks": "system",
    "/api/v1/auth": "security",
    "/api/v1/mfa": "security",
}

# ── Method → Action prefix mapping ───────────────────────────

METHOD_ACTION_MAP = {
    "GET": "view",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


class ActivityCaptureMiddleware(BaseHTTPMiddleware):
    """Middleware that captures HTTP requests as ActivityLog entries.

    This middleware automatically records user actions, billing events,
    system events, etc. into the Activity Store. It runs after the
    request completes and is completely non-blocking (BC-008: never crash).

    The middleware uses the tenant context set by TenantMiddleware
    to get company_id, so it's always tenant-scoped.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip noisy paths
        path = request.url.path

        if path in SKIP_PATHS:
            return await call_next(request)

        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            return await call_next(request)

        # Skip WebSocket upgrades
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        start_time = time.perf_counter()

        # Process the request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # ── Decide whether to log this request ──
        method = request.method
        status_code = response.status_code

        # Skip GET requests to list endpoints (just browsing)
        # But DO log if it returned an error
        if method == "GET" and status_code < 400:
            # Skip list endpoints (no specific entity ID in path)
            path_parts = [p for p in path.split("/") if p]
            # If path has no UUID-like segment, it's a list endpoint
            has_entity_id = any(
                len(p) == 36 and "-" in p  # UUID format
                for p in path_parts
            )
            if not has_entity_id:
                return response

        # ── Capture the activity ──
        try:
            self._capture_activity(request, method, path, status_code, duration_ms)
        except Exception:
            # BC-008: Never crash the request because of activity logging
            logger.debug("activity_capture_non_fatal", exc_info=True)

        return response

    def _capture_activity(
        self,
        request: Request,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Capture a request as an ActivityLog entry.

        This is a synchronous method that runs after the request.
        It opens a new DB session to avoid interfering with the request.
        """
        try:
            # Get company_id from tenant context
            company_id = getattr(request.state, "company_id", None)
            if not company_id:
                # No tenant context — skip (public endpoints, health, etc.)
                return

            # Determine category from route
            category = self._resolve_category(path)

            # Determine action
            action_prefix = METHOD_ACTION_MAP.get(method, "action")
            action = self._resolve_action(path, method, action_prefix)

            # Determine importance
            importance = self._resolve_importance(category, method, status_code)

            # Get actor info
            user_id = getattr(request.state, "user_id", None)
            actor_type = "user" if user_id else "api"
            actor_name = getattr(request.state, "user_email", None)

            # Extract entity info from path
            entity_type, entity_id = self._extract_entity(path)

            # Build details
            details = {
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "method": method,
                "path": path,
            }

            # Build human-readable label
            label = self._build_label(method, path, status_code, category)

            # Get DB session and log
            from database.base import SessionLocal

            db = SessionLocal()
            try:
                from app.services.activity_store import log_activity

                log_activity(
                    db=db,
                    company_id=company_id,
                    category=category,
                    action=action,
                    actor_type=actor_type,
                    actor_id=user_id,
                    actor_name=actor_name,
                    label=label,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    route=path,
                    method=method,
                    details=details,
                    importance=importance,
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.debug("activity_capture_db_failed", exc_info=True)
            finally:
                db.close()

        except Exception:
            logger.debug("activity_capture_failed", exc_info=True)

    def _resolve_category(self, path: str) -> str:
        """Determine the activity category from the route path."""
        for route_prefix, category in ROUTE_CATEGORY_MAP.items():
            if path.startswith(route_prefix):
                return category
        return "system"

    def _resolve_action(self, path: str, method: str, action_prefix: str) -> str:
        """Determine the specific action from path and method."""
        # Special cases for billing
        if "/billing" in path:
            if "subscribe" in path:
                return "subscription_change"
            if "cancel" in path:
                return "subscription_cancel"
            if "upgrade" in path:
                return "upgrade_button_clicked"
            if "downgrade" in path:
                return "downgrade_button_clicked"
            if "refund" in path:
                return "refund_processed"
            if "payment" in path and method in ("POST", "PUT"):
                return "payment_processed"

        # Special cases for tickets
        if "/tickets" in path:
            if method == "POST":
                return "ticket_created"
            if method in ("PUT", "PATCH"):
                return "ticket_updated"
            if method == "DELETE":
                return "ticket_deleted"

        # Special cases for auth
        if "/auth" in path:
            if "login" in path:
                return "user_login"
            if "logout" in path:
                return "user_logout"
            if "register" in path:
                return "user_register"

        # Default: method-based action
        return f"{action_prefix}_{path.split('/')[-1] or 'resource'}"

    def _resolve_importance(self, category: str, method: str, status_code: int) -> str:
        """Determine the importance of this activity."""
        # Errors are always high+
        if status_code >= 500:
            return "critical"
        if status_code >= 400:
            return "medium"

        # Category-based defaults
        if category == "billing" and method in ("POST", "PUT", "PATCH", "DELETE"):
            return "high"
        if category == "security":
            return "high"
        if category == "configuration" and method in ("PUT", "PATCH", "DELETE"):
            return "high"
        if method == "GET":
            return "low"

        return "medium"

    def _extract_entity(self, path: str) -> tuple:
        """Extract entity_type and entity_id from the URL path."""
        parts = [p for p in path.split("/") if p]

        # Look for UUID-like segments
        entity_id = None
        entity_type = None

        for i, part in enumerate(parts):
            # UUID format: 8-4-4-4-12 or 32 hex chars
            if len(part) == 36 and part.count("-") == 4:
                entity_id = part
                # The segment before is likely the entity type
                if i > 0:
                    entity_type = parts[i - 1]
                break

        return entity_type, entity_id

    def _build_label(
        self, method: str, path: str, status_code: int, category: str,
    ) -> str:
        """Build a human-readable label for this activity."""
        method_str = method.upper()
        status_str = f" ({status_code})" if status_code >= 400 else ""

        # Try to make it readable
        if category == "billing":
            return f"Billing: {method_str} {path}{status_str}"
        if category == "security":
            return f"Security: {method_str} {path}{status_str}"
        if category == "workflow":
            return f"Workflow: {method_str} {path}{status_str}"
        if category == "configuration":
            return f"Config: {method_str} {path}{status_str}"
        if category == "channel":
            return f"Channel: {method_str} {path}{status_str}"

        return f"{method_str} {path}{status_str}"
