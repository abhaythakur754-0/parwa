"""
Email Bounce & Complaint Service — Week 13 Day 3 (F-124)

Processes Brevo bounce and complaint webhook events:
1. Hard bounces: Mark email as invalid, stop sending
2. Soft bounces: Retry up to 3 times over 7 days
3. Complaints: Flag contact, permanent suppression (BC-010)
4. Delivery confirmations: Update OutboundEmail status
5. Suppression list management: Prevent sending to invalid addresses
6. Whitelist: Allow sending to previously bounced addresses
7. Deliverability alerts: Notify tenants on reputation risk
8. All events: Store in EmailDeliveryEvent + EmailBounce tables

Building Codes:
- BC-001: Multi-tenant isolation
- BC-003: Idempotent webhook processing (event_id dedup)
- BC-006: Email communication rules (stop sending to invalid emails)
- BC-010: GDPR (complaint = stop all emails permanently)
- BC-012: Errors never block legitimate processing
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.email_utils import run_async_coro, validate_email_address

logger = logging.getLogger("parwa.email_bounce")

# ── Constants ──────────────────────────────────────────────────

# Soft bounce: retry up to 3 times over 7 days
SOFT_BOUNCE_MAX_RETRIES = 3
SOFT_BOUNCE_RETRY_WINDOW_DAYS = 7

# Gmail complaint rate threshold for ops alert (0.1%)
GMAIL_COMPLAINT_RATE_THRESHOLD = 0.001

# Hard bounce reasons that mean permanent failure
HARD_BOUNCE_REASONS = {
    "invalid_domain",
    "invalid_address",
    "does_not_exist",
    "mailbox_not_found",
    "user_unknown",
    "rejected",
    "dns_failure",
    "authentication_failure",
}

# Soft bounce reasons that mean temporary failure
SOFT_BOUNCE_REASONS = {
    "mailbox_full",
    "too_large",
    "timeout",
    "connection_refused",
    "temporary_failure",
    "graylisted",
}


class BounceComplaintService:
    """Processes email bounce and complaint events from Brevo.

    Usage:
        service = BounceComplaintService(db)
        result = service.process_bounce(company_id, bounce_data)
        result = service.process_complaint(company_id, complaint_data)
    """

    def __init__(self, db: Session):
        self.db = db

    def process_bounce(
        self,
        company_id: str,
        bounce_data: dict,
    ) -> dict:
        """Process an email bounce event.

        Determines if hard or soft bounce, updates contact status,
        creates email_bounces record, updates customer_email_status,
        schedules retries for soft bounces, and stores the event.

        Args:
            company_id: Tenant company ID.
            bounce_data: Dict with email, bounce_type, reason,
                message_id, event_id (from Brevo webhook).

        Returns:
            Dict with status, bounce_type, action_taken.
        """
        from database.models.email_delivery_event import EmailDeliveryEvent
        from database.models.email_bounces import EmailBounce

        email = bounce_data.get("email", "")
        reason = bounce_data.get("reason", "").lower()
        bounce_type = bounce_data.get("bounce_type", "").lower()
        message_id = bounce_data.get("message_id", "")
        event_id = bounce_data.get("event_id") or bounce_data.get("brevo_event_id", "")

        if not email:
            return {"status": "error", "error": "Missing email in bounce data"}

        # Validate email format
        if not validate_email_address(email):
            return {"status": "error", "error": f"Invalid email format: {email}"}

        # Determine if hard or soft
        is_hard = self._is_hard_bounce(bounce_type, reason)
        event_type = "hard_bounce" if is_hard else "soft_bounce"

        # Check BC-003 idempotency — already processed?
        if event_id and self._is_event_processed(company_id, event_id):
            logger.info(
                "bounce_already_processed",
                extra={"company_id": company_id, "event_id": event_id},
            )
            return {"status": "duplicate", "event_id": event_id}

        # Detect provider
        provider = self._detect_provider(email, bounce_data)

        # Find the OutboundEmail record
        outbound = self._find_outbound_email(company_id, message_id)

        # Get or create customer email status
        email_status_before = "active"
        email_status_obj = self._get_or_create_email_status(company_id, email)
        if email_status_obj:
            email_status_before = email_status_obj.email_status or "active"

        # Create EmailBounce record (F-124 spec table)
        bounce_record = EmailBounce(
            company_id=company_id,
            customer_email=email,
            bounce_type=event_type,
            bounce_reason=bounce_data.get("reason", ""),
            provider=provider,
            provider_code=bounce_data.get("code", ""),
            event_id=event_id or None,
            related_ticket_id=outbound.ticket_id if outbound else None,
            email_status_before=email_status_before,
        )

        # Create delivery event record
        event = EmailDeliveryEvent(
            company_id=company_id,
            event_type=event_type,
            recipient_email=email,
            brevo_message_id=message_id,
            brevo_event_id=event_id or None,
            outbound_email_id=outbound.id if outbound else None,
            ticket_id=outbound.ticket_id if outbound else None,
            reason=bounce_data.get("reason", ""),
            bounce_type=bounce_type or event_type,
            is_processed=True,
            provider_data=bounce_data,
        )

        action_taken = []

        if is_hard:
            # Hard bounce: mark email as invalid
            self._mark_email_invalid(company_id, email)
            bounce_record.email_status_after = "hard_bounced"
            if email_status_obj:
                email_status_obj.email_status = "hard_bounced"
                email_status_obj.bounce_count = (email_status_obj.bounce_count or 0) + 1
                email_status_obj.last_bounce_at = datetime.now(timezone.utc)
            if outbound:
                outbound.delivery_status = "bounced"
                outbound.bounced_at = datetime.now(timezone.utc)
            action_taken.append("email_marked_invalid")
        else:
            # Soft bounce: check retry count
            retry_count = self._get_soft_bounce_count(company_id, email)
            event.retry_count = retry_count + 1
            event.max_retries = SOFT_BOUNCE_MAX_RETRIES

            if retry_count < SOFT_BOUNCE_MAX_RETRIES:
                # Schedule retry
                next_retry = datetime.now(timezone.utc) + timedelta(
                    days=SOFT_BOUNCE_RETRY_WINDOW_DAYS / SOFT_BOUNCE_MAX_RETRIES,
                )
                event.next_retry_at = next_retry
                bounce_record.email_status_after = "soft_bounced"
                if email_status_obj:
                    email_status_obj.email_status = "soft_bounced"
                    email_status_obj.bounce_count = (
                        email_status_obj.bounce_count or 0
                    ) + 1
                    email_status_obj.last_bounce_at = datetime.now(timezone.utc)
                action_taken.append(f"scheduled_retry_{retry_count + 1}")
                if outbound:
                    outbound.delivery_status = "soft_bounced"
                    outbound.error_message = f"Soft bounce (retry {
                        retry_count + 1}/{SOFT_BOUNCE_MAX_RETRIES})"
            else:
                # Max retries exceeded — treat as hard bounce (suppressed)
                self._mark_email_invalid(company_id, email)
                event.bounce_type = "soft_bounce_max_retries"
                bounce_record.email_status_after = "suppressed"
                if email_status_obj:
                    email_status_obj.email_status = "suppressed"
                    email_status_obj.bounce_count = (
                        email_status_obj.bounce_count or 0
                    ) + 1
                    email_status_obj.last_bounce_at = datetime.now(timezone.utc)
                    email_status_obj.suppressed_at = datetime.now(timezone.utc)
                if outbound:
                    outbound.delivery_status = "failed"
                    outbound.error_message = (
                        f"Soft bounce max retries ({SOFT_BOUNCE_MAX_RETRIES}) exceeded"
                    )
                action_taken.append("soft_bounce_max_retries_treated_as_hard")

        self.db.add(bounce_record)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        # Emit real-time event (BC-005)
        self._emit_delivery_event(
            company_id=company_id,
            event_type=event_type,
            email=email,
            event_id=str(event.id),
            ticket_id=outbound.ticket_id if outbound else None,
        )

        logger.info(
            "bounce_processed",
            extra={
                "company_id": company_id,
                "email": email,
                "bounce_type": event_type,
                "actions": action_taken,
                "event_id": str(event.id),
            },
        )

        return {
            "status": "processed",
            "event_type": event_type,
            "email": email,
            "actions": action_taken,
            "event_id": str(event.id),
        }

    def process_complaint(
        self,
        company_id: str,
        complaint_data: dict,
    ) -> dict:
        """Process a spam complaint event.

        Marks the contact as complained (BC-010: stop all emails permanently).
        Creates email_bounces record and customer_email_status update.

        Args:
            company_id: Tenant company ID.
            complaint_data: Dict with email, complaint_type, reason,
                message_id, event_id.

        Returns:
            Dict with status and action_taken.
        """
        from database.models.email_delivery_event import EmailDeliveryEvent
        from database.models.email_bounces import EmailBounce

        email = complaint_data.get("email", "")
        reason = complaint_data.get("reason", "")
        complaint_type = complaint_data.get("complaint_type", "unknown")
        message_id = complaint_data.get("message_id", "")
        event_id = complaint_data.get("event_id") or complaint_data.get(
            "brevo_event_id", ""
        )

        if not email:
            return {"status": "error", "error": "Missing email in complaint data"}

        # BC-003 idempotency
        if event_id and self._is_event_processed(company_id, event_id):
            logger.info(
                "complaint_already_processed",
                extra={"company_id": company_id, "event_id": event_id},
            )
            return {"status": "duplicate", "event_id": event_id}

        # Find outbound email
        outbound = self._find_outbound_email(company_id, message_id)
        provider = self._detect_provider(email, complaint_data)

        # Get or create customer email status
        email_status_obj = self._get_or_create_email_status(company_id, email)
        status_before = email_status_obj.email_status if email_status_obj else "active"

        # Create EmailBounce record
        bounce_record = EmailBounce(
            company_id=company_id,
            customer_email=email,
            bounce_type="complaint",
            bounce_reason=reason,
            provider=provider,
            event_id=event_id or None,
            related_ticket_id=outbound.ticket_id if outbound else None,
            email_status_before=status_before,
            email_status_after="complained",
        )

        # Create delivery event
        event = EmailDeliveryEvent(
            company_id=company_id,
            event_type="complaint",
            recipient_email=email,
            brevo_message_id=message_id,
            brevo_event_id=event_id or None,
            outbound_email_id=outbound.id if outbound else None,
            ticket_id=outbound.ticket_id if outbound else None,
            reason=reason,
            bounce_type=complaint_type,
            is_processed=True,
            provider_data=complaint_data,
        )

        # Mark email as complained (BC-010: stop all emails permanently)
        self._mark_email_complained(company_id, email)
        if email_status_obj:
            email_status_obj.email_status = "complained"
            email_status_obj.complaint_count = (
                email_status_obj.complaint_count or 0
            ) + 1
            email_status_obj.last_complaint_at = datetime.now(timezone.utc)

        if outbound:
            outbound.delivery_status = "complaint"

        self.db.add(bounce_record)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        # Emit real-time event
        self._emit_delivery_event(
            company_id=company_id,
            event_type="complaint",
            email=email,
            event_id=str(event.id),
            ticket_id=outbound.ticket_id if outbound else None,
        )

        # Check Gmail complaint rate (BC-006)
        self._check_gmail_complaint_rate(company_id)

        # Create deliverability alert for complaint
        self._create_deliverability_alert(
            company_id=company_id,
            alert_type="complaint_spike",
            severity="critical",
            message=f"Spam complaint received for {email}. Email permanently suppressed.",
            metric_value=0.0,
            threshold=0.0,
        )

        logger.warning(
            "spam_complaint_processed",
            extra={
                "company_id": company_id,
                "email": email,
                "complaint_type": complaint_type,
                "provider": provider,
                "event_id": str(event.id),
            },
        )

        return {
            "status": "processed",
            "event_type": "complaint",
            "email": email,
            "actions": ["email_marked_complained"],
            "event_id": str(event.id),
        }

    def process_delivered(
        self,
        company_id: str,
        delivery_data: dict,
    ) -> dict:
        """Process a delivery confirmation event.

        Updates OutboundEmail status to "delivered" and stores the event.

        Args:
            company_id: Tenant company ID.
            delivery_data: Dict with email, message_id, event_id.

        Returns:
            Dict with status.
        """
        from database.models.email_delivery_event import EmailDeliveryEvent

        email = delivery_data.get("email", "")
        message_id = delivery_data.get("message_id", "")
        event_id = delivery_data.get("event_id") or delivery_data.get(
            "brevo_event_id", ""
        )

        # BC-003 idempotency
        if event_id and self._is_event_processed(company_id, event_id):
            return {"status": "duplicate", "event_id": event_id}

        outbound = self._find_outbound_email(company_id, message_id)

        event = EmailDeliveryEvent(
            company_id=company_id,
            event_type="delivered",
            recipient_email=email,
            brevo_message_id=message_id,
            brevo_event_id=event_id or None,
            outbound_email_id=outbound.id if outbound else None,
            ticket_id=outbound.ticket_id if outbound else None,
            is_processed=True,
            provider_data=delivery_data,
        )

        if outbound:
            outbound.delivery_status = "delivered"
            outbound.delivered_at = datetime.now(timezone.utc)

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return {
            "status": "processed",
            "event_type": "delivered",
            "email": email,
            "event_id": str(event.id),
        }

    # ── Suppression List ────────────────────────────────────────

    def is_email_suppressed(self, company_id: str, email: str) -> bool:
        """Check if an email address is suppressed from receiving emails.

        Checks customer_email_status table for bounced/complained/suppressed.

        Args:
            company_id: Tenant company ID.
            email: Email address to check.

        Returns:
            True if email is suppressed.
        """
        from database.models.email_bounces import CustomerEmailStatus

        status = (
            self.db.query(CustomerEmailStatus)
            .filter(
                CustomerEmailStatus.company_id == company_id,
                CustomerEmailStatus.customer_email == email.lower().strip(),
            )
            .first()
        )

        if not status:
            return False

        if status.whitelisted:
            return False

        return status.email_status in ("hard_bounced", "complained", "suppressed")

    def get_email_status(self, company_id: str, email: str) -> dict:
        """Get full delivery status for an email address.

        Returns status from customer_email_status plus event counts.

        Args:
            company_id: Tenant company ID.
            email: Email address.

        Returns:
            Dict with delivery status summary.
        """
        from database.models.email_bounces import CustomerEmailStatus
        from database.models.email_delivery_event import EmailDeliveryEvent

        status_obj = (
            self.db.query(CustomerEmailStatus)
            .filter(
                CustomerEmailStatus.company_id == company_id,
                CustomerEmailStatus.customer_email == email.lower().strip(),
            )
            .first()
        )

        # Get event counts
        stats = (
            self.db.query(
                EmailDeliveryEvent.event_type,
                func.count(EmailDeliveryEvent.id).label("count"),
            )
            .filter(
                EmailDeliveryEvent.company_id == company_id,
                EmailDeliveryEvent.recipient_email == email.lower().strip(),
            )
            .group_by(EmailDeliveryEvent.event_type)
            .all()
        )

        status_map = {}
        for event_type, count in stats:
            status_map[event_type] = count

        is_valid = True
        is_complained = False
        email_status = "active"
        whitelisted = False

        if status_obj:
            email_status = status_obj.email_status or "active"
            is_valid = email_status == "active"
            is_complained = email_status == "complained"
            whitelisted = bool(status_obj.whitelisted)
            if whitelisted:
                is_valid = True

        return {
            "email": email,
            "is_valid": is_valid,
            "is_complained": is_complained,
            "can_send": is_valid and not is_complained,
            "email_status": email_status,
            "hard_bounces": status_map.get("hard_bounce", 0),
            "soft_bounces": status_map.get("soft_bounce", 0),
            "complaints": status_map.get("complaint", 0),
            "delivered": status_map.get("delivered", 0),
            "whitelisted": whitelisted,
        }

    # ── Whitelist ────────────────────────────────────────────────

    def whitelist_email(
        self,
        company_id: str,
        email: str,
        justification: str,
        user_id: Optional[str] = None,
    ) -> dict:
        """Whitelist a previously bounced/suppressed email.

        Allows sending to the email again. Note: if a NEW bounce
        comes after whitelisting, the whitelist is preserved but
        an alert is sent recommending review (BC-006 edge case).

        Args:
            company_id: Tenant company ID.
            email: Email to whitelist.
            justification: Reason for whitelisting.
            user_id: Admin user who whitelisted.

        Returns:
            Dict with status.
        """
        from database.models.email_bounces import EmailBounce, CustomerEmailStatus

        email = email.lower().strip()

        # Update customer_email_status
        status_obj = (
            self.db.query(CustomerEmailStatus)
            .filter(
                CustomerEmailStatus.company_id == company_id,
                CustomerEmailStatus.customer_email == email,
            )
            .first()
        )

        if status_obj:
            status_obj.whitelisted = True

        # Update all non-complaint bounces for this email
        self.db.query(EmailBounce).filter(
            EmailBounce.company_id == company_id,
            EmailBounce.customer_email == email,
            EmailBounce.bounce_type != "complaint",
            EmailBounce.whitelisted is False,
        ).update(
            {
                "whitelisted": True,
                "whitelist_justification": justification,
                "whitelisted_by": user_id,
                "whitelisted_at": datetime.now(timezone.utc),
            },
            synchronize_session="fetch",
        )

        self.db.commit()

        logger.info(
            "email_whitelisted",
            extra={
                "company_id": company_id,
                "email": email,
                "user_id": user_id,
            },
        )

        return {"status": "whitelisted", "email": email}

    # ── Listing & Stats ──────────────────────────────────────────

    def list_bounces(
        self,
        company_id: str,
        status: str = "all",
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """List bounce/complaint events for a tenant.

        Args:
            company_id: Tenant company ID.
            status: Filter by type (all/soft/hard/complaint).
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Dict with bounces list and pagination.
        """
        from database.models.email_bounces import EmailBounce

        query = self.db.query(EmailBounce).filter(EmailBounce.company_id == company_id)

        if status != "all":
            query = query.filter(EmailBounce.bounce_type == status)

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = (
            query.order_by(EmailBounce.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return {
            "bounces": [
                {
                    "id": str(b.id),
                    "email": b.customer_email,
                    "type": b.bounce_type,
                    "reason": b.bounce_reason,
                    "provider": b.provider,
                    "event_date": b.created_at.isoformat() if b.created_at else None,
                    "status": b.email_status_after,
                    "whitelisted": b.whitelisted,
                    "ticket_count": 1 if b.related_ticket_id else 0,
                }
                for b in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_stats(self, company_id: str, range_days: int = 7) -> dict:
        """Get bounce/complaint statistics for a tenant.

        Args:
            company_id: Tenant company ID.
            range_days: Number of days to look back.

        Returns:
            Dict with bounce stats and trends.
        """
        from database.models.email_bounces import EmailBounce, CustomerEmailStatus

        since = datetime.now(timezone.utc) - timedelta(days=range_days)
        prev_since = since - timedelta(days=range_days)

        # Current period counts
        try:
            current_bounces = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.created_at >= since,
                    EmailBounce.bounce_type.in_(["hard_bounce", "soft_bounce"]),
                )
                .scalar()
            ) or 0
        except Exception:
            current_bounces = 0

        try:
            current_hard = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.created_at >= since,
                    EmailBounce.bounce_type == "hard_bounce",
                )
                .scalar()
            ) or 0
        except Exception:
            current_hard = 0

        try:
            current_soft = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.created_at >= since,
                    EmailBounce.bounce_type == "soft_bounce",
                )
                .scalar()
            ) or 0
        except Exception:
            current_soft = 0

        try:
            current_complaints = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.created_at >= since,
                    EmailBounce.bounce_type == "complaint",
                )
                .scalar()
            ) or 0
        except Exception:
            current_complaints = 0

        # Suppressed count
        try:
            suppressed = (
                self.db.query(func.count(CustomerEmailStatus.id))
                .filter(
                    CustomerEmailStatus.company_id == company_id,
                    CustomerEmailStatus.email_status.in_(
                        ["hard_bounced", "complained", "suppressed"]
                    ),
                    CustomerEmailStatus.whitelisted is False,
                )
                .scalar()
            ) or 0
        except Exception:
            suppressed = 0

        # Previous period for trend comparison
        try:
            prev_bounces = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.created_at >= prev_since,
                    EmailBounce.created_at < since,
                    EmailBounce.bounce_type.in_(["hard_bounce", "soft_bounce"]),
                )
                .scalar()
            ) or 0
        except Exception:
            prev_bounces = 0

        # Trend calculation
        if prev_bounces > 0:
            change = (current_bounces - prev_bounces) / prev_bounces
            if change > 0.2:
                trend = "worsening"
            elif change < -0.2:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "stable" if current_bounces == 0 else "worsening"

        # Bounce rate (bounces / total outbound)
        bounce_rate = 0.0
        try:
            from database.models.outbound_email import OutboundEmail

            total_sent = (
                self.db.query(func.count(OutboundEmail.id))
                .filter(
                    OutboundEmail.company_id == company_id,
                    OutboundEmail.created_at >= since,
                )
                .scalar()
            ) or 0
            if total_sent > 0:
                bounce_rate = round(current_bounces / total_sent, 4)
        except Exception:
            total_sent = 0

        complaint_rate = 0.0
        if total_sent > 0:
            complaint_rate = round(current_complaints / total_sent, 4)

        return {
            "total_bounces": current_bounces,
            "hard_bounces": current_hard,
            "soft_bounces": current_soft,
            "complaints": current_complaints,
            "bounce_rate": bounce_rate,
            "complaint_rate": complaint_rate,
            "trend": trend,
            "range_days": range_days,
            "suppressed_count": suppressed,
        }

    def get_digest(self, company_id: str) -> dict:
        """Get deliverability digest for a tenant.

        Returns critical alerts and summary since last digest.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with critical_alerts and summary.
        """
        from database.models.email_bounces import EmailDeliverabilityAlert, EmailBounce

        # Get unacknowledged critical alerts
        try:
            alerts = (
                self.db.query(EmailDeliverabilityAlert)
                .filter(
                    EmailDeliverabilityAlert.company_id == company_id,
                    EmailDeliverabilityAlert.acknowledged is False,
                    EmailDeliverabilityAlert.severity.in_(["high", "critical"]),
                )
                .order_by(EmailDeliverabilityAlert.created_at.desc())
                .limit(20)
                .all()
            )
        except Exception:
            alerts = []

        # Get recent summary (last 24h)
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        try:
            recent_bounces = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.created_at >= since,
                )
                .scalar()
            ) or 0
        except Exception:
            recent_bounces = 0

        try:
            recent_complaints = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.created_at >= since,
                    EmailBounce.bounce_type == "complaint",
                )
                .scalar()
            ) or 0
        except Exception:
            recent_complaints = 0

        return {
            "since_last_digest": since.isoformat(),
            "critical_alerts": [
                {
                    "id": str(a.id),
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "metric_value": a.metric_value,
                    "threshold": a.threshold,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "acknowledged": a.acknowledged,
                }
                for a in alerts
            ],
            "summary": {
                "bounces_last_24h": recent_bounces,
                "complaints_last_24h": recent_complaints,
                "critical_alert_count": len(alerts),
            },
        }

    def get_soft_bounces_for_retry(self, company_id: Optional[str] = None) -> list:
        """Get soft bounces that are due for retry.

        Args:
            company_id: Optional tenant filter.

        Returns:
            List of EmailDeliveryEvent records due for retry.
        """
        from database.models.email_delivery_event import EmailDeliveryEvent

        now = datetime.now(timezone.utc)
        query = self.db.query(EmailDeliveryEvent).filter(
            EmailDeliveryEvent.event_type == "soft_bounce",
            EmailDeliveryEvent.is_processed,
            EmailDeliveryEvent.retry_count < SOFT_BOUNCE_MAX_RETRIES,
            EmailDeliveryEvent.next_retry_at <= now,
        )
        if company_id:
            query = query.filter(EmailDeliveryEvent.company_id == company_id)
        return query.all()

    def get_email_delivery_status(self, company_id: str, email: str) -> dict:
        """Get delivery status summary for an email address.

        Returns counts of each event type and whether the email
        is marked as invalid or complained.

        Args:
            company_id: Tenant company ID.
            email: Email address to check.

        Returns:
            Dict with delivery status summary.
        """
        # Delegate to the richer get_email_status method
        return self.get_email_status(company_id, email)

    # ── Private Methods ─────────────────────────────────────────

    @staticmethod
    def _is_hard_bounce(bounce_type: str, reason: str) -> bool:
        """Determine if a bounce is hard (permanent) or soft (temporary)."""
        combined = f"{bounce_type} {reason}".lower()

        # Explicit hard bounce indicators
        for hard_indicator in HARD_BOUNCE_REASONS:
            if hard_indicator in combined:
                return True

        # Explicit soft bounce indicators
        for soft_indicator in SOFT_BOUNCE_REASONS:
            if soft_indicator in combined:
                return False

        # Default: if type contains "hard", it's hard; otherwise soft
        return "hard" in combined or "invalid" in combined

    @staticmethod
    def _detect_provider(email: str, event_data: dict) -> str:
        """Detect email provider from email domain."""
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if "gmail.com" in domain or "googlemail.com" in domain:
            return "gmail"
        elif "outlook.com" in domain or "hotmail.com" in domain or "live.com" in domain:
            return "outlook"
        elif "yahoo.com" in domain or "ymail.com" in domain:
            return "yahoo"
        return "other"

    def _find_outbound_email(
        self,
        company_id: str,
        message_id: str,
    ) -> Optional[object]:
        """Find an OutboundEmail record by Brevo message_id."""
        from database.models.outbound_email import OutboundEmail

        if not message_id:
            return None
        return (
            self.db.query(OutboundEmail)
            .filter(
                OutboundEmail.company_id == company_id,
                OutboundEmail.brevo_message_id == message_id,
            )
            .first()
        )

    def _is_event_processed(
        self,
        company_id: str,
        event_id: str,
    ) -> bool:
        """BC-003: Check if an event was already processed."""
        from database.models.email_delivery_event import EmailDeliveryEvent

        if not event_id:
            return False
        count = (
            self.db.query(func.count(EmailDeliveryEvent.id))
            .filter(
                EmailDeliveryEvent.company_id == company_id,
                EmailDeliveryEvent.brevo_event_id == event_id,
            )
            .scalar()
        ) or 0
        return count > 0

    def _get_soft_bounce_count(
        self,
        company_id: str,
        email: str,
    ) -> int:
        """Get the number of soft bounces for an email in the retry window."""
        from database.models.email_delivery_event import EmailDeliveryEvent

        window_start = datetime.now(timezone.utc) - timedelta(
            days=SOFT_BOUNCE_RETRY_WINDOW_DAYS
        )
        return (
            self.db.query(func.count(EmailDeliveryEvent.id))
            .filter(
                EmailDeliveryEvent.company_id == company_id,
                EmailDeliveryEvent.recipient_email == email,
                EmailDeliveryEvent.event_type == "soft_bounce",
                EmailDeliveryEvent.created_at >= window_start,
            )
            .scalar()
        ) or 0

    def _get_or_create_email_status(
        self,
        company_id: str,
        email: str,
    ) -> Optional[object]:
        """Get or create customer email status record."""
        from database.models.email_bounces import CustomerEmailStatus

        status = (
            self.db.query(CustomerEmailStatus)
            .filter(
                CustomerEmailStatus.company_id == company_id,
                CustomerEmailStatus.customer_email == email.lower().strip(),
            )
            .first()
        )

        if not status:
            status = CustomerEmailStatus(
                company_id=company_id,
                customer_email=email.lower().strip(),
                email_status="active",
            )
            self.db.add(status)
            self.db.flush()

        return status

    def _mark_email_invalid(
        self,
        company_id: str,
        email: str,
    ) -> None:
        """Mark a customer's email as invalid (hard bounce)."""
        from database.models.tickets import Customer

        customer = (
            self.db.query(Customer)
            .filter(
                Customer.company_id == company_id,
                Customer.email == email,
            )
            .first()
        )
        if customer:
            if hasattr(customer, "email_valid"):
                customer.email_valid = False
            if hasattr(customer, "email_status"):
                customer.email_status = "bounced"
            logger.info(
                "email_marked_invalid",
                extra={"company_id": company_id, "email": email},
            )

    def _mark_email_complained(
        self,
        company_id: str,
        email: str,
    ) -> None:
        """Mark a customer's email as complained (BC-010: stop all emails)."""
        from database.models.tickets import Customer

        customer = (
            self.db.query(Customer)
            .filter(
                Customer.company_id == company_id,
                Customer.email == email,
            )
            .first()
        )
        if customer:
            if hasattr(customer, "email_opt_out"):
                customer.email_opt_out = True
            if hasattr(customer, "email_status"):
                customer.email_status = "complained"
            if hasattr(customer, "email_valid"):
                customer.email_valid = False
            logger.warning(
                "email_marked_complained",
                extra={"company_id": company_id, "email": email},
            )

    def _check_gmail_complaint_rate(self, company_id: str) -> None:
        """Check Gmail complaint rate and alert if > 0.1% (BC-006)."""
        try:
            from database.models.email_bounces import EmailBounce

            since = datetime.now(timezone.utc) - timedelta(days=30)

            total_gmail = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.provider == "gmail",
                    EmailBounce.created_at >= since,
                )
                .scalar()
            ) or 0

            if total_gmail == 0:
                return

            gmail_complaints = (
                self.db.query(func.count(EmailBounce.id))
                .filter(
                    EmailBounce.company_id == company_id,
                    EmailBounce.provider == "gmail",
                    EmailBounce.bounce_type == "complaint",
                    EmailBounce.created_at >= since,
                )
                .scalar()
            ) or 0

            rate = gmail_complaints / total_gmail
            if rate > GMAIL_COMPLAINT_RATE_THRESHOLD:
                self._create_deliverability_alert(
                    company_id=company_id,
                    alert_type="reputation_warning",
                    severity="critical",
                    message=(
                        f"Gmail complaint rate ({rate:.2%}) exceeds "
                        f"threshold ({GMAIL_COMPLAINT_RATE_THRESHOLD:.2%}). "
                        "Sender reputation at risk."
                    ),
                    metric_value=rate,
                    threshold=GMAIL_COMPLAINT_RATE_THRESHOLD,
                )
        except Exception as exc:
            logger.warning(
                "gmail_complaint_rate_check_failed", extra={"error": str(exc)[:200]}
            )

    def _create_deliverability_alert(
        self,
        company_id: str,
        alert_type: str,
        severity: str,
        message: str,
        metric_value: float,
        threshold: float,
    ) -> None:
        """Create a deliverability alert for the tenant."""
        from database.models.email_bounces import EmailDeliverabilityAlert

        alert = EmailDeliverabilityAlert(
            company_id=company_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_value=metric_value,
            threshold=threshold,
        )
        self.db.add(alert)
        self.db.flush()

        logger.warning(
            "deliverability_alert_created",
            extra={
                "company_id": company_id,
                "alert_type": alert_type,
                "severity": severity,
            },
        )

    def _emit_delivery_event(
        self,
        company_id: str,
        event_type: str,
        email: str,
        event_id: str,
        ticket_id: Optional[str] = None,
    ) -> None:
        """Emit real-time Socket.io event for delivery status (BC-005)."""
        try:
            from app.core.event_emitter import emit_ticket_event

            run_async_coro(
                emit_ticket_event(
                    company_id=company_id,
                    event_type="email:delivery_event",
                    payload={
                        "event_type": event_type,
                        "email": email,
                        "delivery_event_id": event_id,
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                    },
                ),
            )
        except Exception:
            pass  # Non-critical
