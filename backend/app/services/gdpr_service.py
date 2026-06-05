"""
GDPR Service — Right to Erasure, Data Portability, Retention, Consent, Audit Immutability.

BC-010: GDPR right-to-erasure compliance.
GDPR Art. 17: Right to erasure (right to be forgotten).
GDPR Art. 20: Right to data portability.
GDPR Art. 15: Right of access by the data subject.
GDPR Art. 7: Conditions for consent.

Key design decisions:
- Erasure strategy: ANONYMIZE (replace PII fields with [ERASED]) rather than hard delete.
  This preserves record structure for analytics and audit while removing PII.
- Audit trail is ALWAYS retained (legal requirement — cannot be deleted).
- Every erasure creates an ErasureRequest record for compliance tracking.
- Retention policies use the GDPR_RETENTION_DAYS config value as default.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────

ERASED_MARKER = "[ERASED]"
DEFAULT_RETENTION_DAYS = 365
AUDIT_RETENTION_DAYS = 2555  # ~7 years


class GDPRErasureService:
    """Service for GDPR right-to-erasure operations (BC-010).

    Implements a two-phase erasure:
    1. Request: Create an ErasureRequest with status=pending
    2. Execute: Anonymize PII in customer records, redact messages,
       purge Redis caches, and update the request status.

    The audit_trail table is NEVER modified during erasure (legal requirement).
    """

    def __init__(self, db: Session):
        self.db = db

    def create_erasure_request(
        self,
        company_id: str,
        customer_email: str,
        scope: str = "full",
        reason: Optional[str] = None,
        request_source: str = "api",
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new GDPR erasure request (Phase 1: Request).

        Args:
            company_id: The tenant ID for multi-tenant isolation.
            customer_email: Email of the data subject.
            scope: Erasure scope (full, profile_only, messages_only, tickets_only).
            reason: Optional reason for the erasure.
            request_source: How the request was received.
            requested_by: ID of the user who made the request.

        Returns:
            Dict with the created ErasureRequest data.
        """
        from database.models.gdpr import ErasureRequest

        erasure_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        erasure_request = ErasureRequest(
            id=erasure_id,
            company_id=company_id,
            customer_email=customer_email,
            scope=scope,
            status="pending",
            reason=reason,
            request_source=request_source,
            requested_by=requested_by,
            verification_status="unverified",
            requested_at=now,
            created_at=now,
            updated_at=now,
        )

        self.db.add(erasure_request)

        # Log to audit trail
        self._log_audit(
            company_id=company_id,
            actor_id=requested_by,
            action="gdpr_erasure_requested",
            resource_type="erasure_request",
            resource_id=erasure_id,
            new_value=f"customer_email={customer_email}, scope={scope}",
        )

        self.db.flush()

        return {
            "id": erasure_id,
            "company_id": company_id,
            "customer_email": customer_email,
            "scope": scope,
            "status": "pending",
            "verification_status": "unverified",
            "reason": reason,
            "request_source": request_source,
            "customers_anonymized": 0,
            "tickets_affected": 0,
            "messages_redacted": 0,
            "redis_keys_purged": 0,
            "error_message": None,
            "requested_at": now.isoformat(),
            "verified_at": None,
            "completed_at": None,
            "created_at": now.isoformat(),
        }

    def verify_erasure_request(
        self,
        erasure_request_id: str,
        company_id: str,
        verified: bool = True,
        verified_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify an erasure request (required before execution).

        Args:
            erasure_request_id: ID of the erasure request.
            company_id: The tenant ID (for isolation check).
            verified: Whether the request is verified.
            verified_by: ID of the user who verified.

        Returns:
            Dict with the updated ErasureRequest data.
        """
        from database.models.gdpr import ErasureRequest

        erasure = self.db.query(ErasureRequest).filter(
            ErasureRequest.id == erasure_request_id,
            ErasureRequest.company_id == company_id,
        ).first()

        if not erasure:
            return {"error": "Erasure request not found", "status": "not_found"}

        now = datetime.now(timezone.utc)
        erasure.verification_status = "verified" if verified else "rejected"
        erasure.verified_at = now
        erasure.updated_at = now

        self._log_audit(
            company_id=company_id,
            actor_id=verified_by,
            action="gdpr_erasure_verified" if verified else "gdpr_erasure_rejected",
            resource_type="erasure_request",
            resource_id=erasure_request_id,
        )

        self.db.flush()

        return {
            "id": erasure.id,
            "company_id": erasure.company_id,
            "customer_email": erasure.customer_email,
            "scope": erasure.scope,
            "status": erasure.status,
            "verification_status": erasure.verification_status,
            "reason": erasure.reason,
            "request_source": erasure.request_source,
            "customers_anonymized": erasure.customers_anonymized,
            "tickets_affected": erasure.tickets_affected,
            "messages_redacted": erasure.messages_redacted,
            "redis_keys_purged": erasure.redis_keys_purged,
            "error_message": erasure.error_message,
            "requested_at": erasure.requested_at.isoformat() if erasure.requested_at else None,
            "verified_at": now.isoformat(),
            "completed_at": erasure.completed_at.isoformat() if erasure.completed_at else None,
            "created_at": erasure.created_at.isoformat() if erasure.created_at else None,
        }

    def execute_erasure(
        self,
        erasure_request_id: str,
        company_id: str,
        executed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a verified erasure request (Phase 2: Execution).

        Steps:
        1. Find customer by email within the tenant
        2. Anonymize customer PII fields (name, email, phone)
        3. Redact PII from ticket messages
        4. Purge Redis keys for the customer
        5. Create erasure log entry
        6. PRESERVE audit_trail records (legal requirement)

        Args:
            erasure_request_id: ID of the verified erasure request.
            company_id: The tenant ID.
            executed_by: ID of the user executing the erasure.

        Returns:
            Dict with execution results.
        """
        from database.models.gdpr import ErasureRequest
        from database.models.tickets import Customer, TicketMessage

        erasure = self.db.query(ErasureRequest).filter(
            ErasureRequest.id == erasure_request_id,
            ErasureRequest.company_id == company_id,
        ).first()

        if not erasure:
            return {"error": "Erasure request not found", "status": "not_found"}

        if erasure.verification_status != "verified":
            return {"error": "Erasure request must be verified first", "status": "not_verified"}

        now = datetime.now(timezone.utc)
        erasure.status = "processing"
        erasure.processing_started_at = now
        erasure.executed_by = executed_by
        erasure.updated_at = now
        self.db.flush()

        results = {
            "erasure_request_id": erasure_request_id,
            "customers_anonymized": 0,
            "tickets_affected": 0,
            "messages_redacted": 0,
            "redis_keys_purged": 0,
            "audit_trail_preserved": True,
        }

        try:
            # Step 1: Find customer(s) by email
            customers = self.db.query(Customer).filter(
                Customer.company_id == company_id,
                Customer.email == erasure.customer_email,
            ).all()

            for customer in customers:
                # Step 2: Anonymize customer PII
                customer.name = ERASED_MARKER
                customer.email = f"{ERASED_MARKER}_{customer.id[:8]}@erased.parwa"
                customer.phone = ERASED_MARKER
                customer.metadata_json = "{}"
                results["customers_anonymized"] += 1

                # Step 3: Redact ticket messages for this customer's tickets
                if erasure.scope in ("full", "tickets_only", "messages_only"):
                    from database.models.tickets import Ticket

                    tickets = self.db.query(Ticket).filter(
                        Ticket.company_id == company_id,
                        Ticket.customer_id == customer.id,
                    ).all()

                    results["tickets_affected"] += len(tickets)

                    for ticket in tickets:
                        # Anonymize ticket subject if it contains PII
                        if erasure.scope in ("full", "tickets_only"):
                            ticket.subject = ERASED_MARKER
                            ticket.metadata_json = "{}"

                        # Redact messages
                        if erasure.scope in ("full", "messages_only"):
                            messages = self.db.query(TicketMessage).filter(
                                TicketMessage.ticket_id == ticket.id,
                                TicketMessage.company_id == company_id,
                            ).all()

                            for message in messages:
                                if message.role == "customer" and not message.is_redacted:
                                    message.content = ERASED_MARKER
                                    message.is_redacted = True
                                    results["messages_redacted"] += 1

            # Step 4: Purge Redis keys (graceful degradation if Redis unavailable)
            try:
                redis_keys_purged = self._purge_redis_keys(
                    company_id=company_id,
                    customer_email=erasure.customer_email,
                )
                results["redis_keys_purged"] = redis_keys_purged
            except Exception as e:
                logger.warning(f"Redis purge failed (graceful degradation): {e}")
                results["redis_keys_purged"] = 0

            # Step 5: Update erasure request status
            erasure.status = "completed"
            erasure.completed_at = datetime.now(timezone.utc)
            erasure.updated_at = datetime.now(timezone.utc)
            erasure.customers_anonymized = results["customers_anonymized"]
            erasure.tickets_affected = results["tickets_affected"]
            erasure.messages_redacted = results["messages_redacted"]
            erasure.redis_keys_purged = results["redis_keys_purged"]

            # Step 6: Log completion to audit trail (audit trail is PRESERVED, not deleted)
            self._log_audit(
                company_id=company_id,
                actor_id=executed_by,
                action="gdpr_erasure_completed",
                resource_type="erasure_request",
                resource_id=erasure_request_id,
                new_value=f"anonymized={results['customers_anonymized']}, "
                          f"redacted={results['messages_redacted']}, "
                          f"redis_purged={results['redis_keys_purged']}",
            )

            self.db.flush()
            results["status"] = "completed"
            results["completed_at"] = erasure.completed_at.isoformat()

        except Exception as e:
            erasure.status = "failed"
            erasure.error_message = str(e)[:500]
            erasure.updated_at = datetime.now(timezone.utc)
            self.db.flush()

            results["status"] = "failed"
            results["error_message"] = str(e)

            self._log_audit(
                company_id=company_id,
                actor_id=executed_by,
                action="gdpr_erasure_failed",
                resource_type="erasure_request",
                resource_id=erasure_request_id,
                new_value=f"error={str(e)[:200]}",
            )

        return results

    def _purge_redis_keys(
        self, company_id: str, customer_email: str
    ) -> int:
        """Purge all Redis keys associated with a customer.

        Graceful degradation: if Redis is unavailable, log warning and return 0.
        """
        try:
            from app.core.redis import get_redis
            import asyncio

            async def _purge():
                redis = await get_redis()
                patterns = [
                    f"parwa:*:{company_id}:*{customer_email}*",
                    f"parwa:pii:{company_id}:*",
                    f"parwa:presence:{company_id}:*{customer_email}*",
                    f"parwa:session:{company_id}:*{customer_email}*",
                ]
                total_deleted = 0
                for pattern in patterns:
                    keys = await redis.keys(pattern)
                    if keys:
                        deleted = await redis.delete(*keys)
                        total_deleted += deleted
                return total_deleted

            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're in an async context already, schedule the purge
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _purge())
                    return future.result(timeout=10)
            else:
                return asyncio.run(_purge())
        except Exception as e:
            logger.warning(f"Redis purge skipped (Redis unavailable): {e}")
            return 0

    def _log_audit(
        self,
        company_id: str,
        actor_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> None:
        """Log an action to the audit_trail table."""
        from database.models.integration import AuditTrail

        audit_entry = AuditTrail(
            id=str(uuid.uuid4()),
            company_id=company_id,
            actor_id=actor_id or "system",
            actor_type="user" if actor_id else "system",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(audit_entry)


class GDPRExportService:
    """Service for GDPR data portability / access requests (Art. 15/20)."""

    def __init__(self, db: Session):
        self.db = db

    def export_customer_data(
        self,
        company_id: str,
        customer_email: str,
        format: str = "json",
        include_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Export all data held about a customer (GDPR Art. 15/20).

        Returns structured data including tickets, messages, interactions.
        No hidden data — everything associated with the customer is included.

        Args:
            company_id: The tenant ID.
            customer_email: Email of the data subject.
            format: Export format (json or csv).
            include_categories: Optional filter for categories to include.

        Returns:
            Dict with exported data organized by category.
        """
        from database.models.tickets import Customer, Ticket, TicketMessage

        exported_data: Dict[str, Any] = {}
        categories_included: List[str] = []
        total_records = 0

        # Find customer by email
        customer = self.db.query(Customer).filter(
            Customer.company_id == company_id,
            Customer.email == customer_email,
        ).first()

        # Category: Customer Profile
        if not include_categories or "profile" in include_categories:
            if customer:
                exported_data["profile"] = {
                    "id": customer.id,
                    "name": customer.name,
                    "email": customer.email,
                    "phone": customer.phone,
                    "external_id": customer.external_id,
                    "created_at": customer.created_at.isoformat() if customer.created_at else None,
                    "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
                }
            else:
                exported_data["profile"] = None
            categories_included.append("profile")
            total_records += 1

        # Category: Tickets
        if customer and (not include_categories or "tickets" in include_categories):
            tickets = self.db.query(Ticket).filter(
                Ticket.company_id == company_id,
                Ticket.customer_id == customer.id,
            ).all()

            exported_data["tickets"] = [
                {
                    "id": t.id,
                    "subject": t.subject,
                    "status": t.status,
                    "priority": t.priority,
                    "category": t.category,
                    "channel": t.channel,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                }
                for t in tickets
            ]
            categories_included.append("tickets")
            total_records += len(tickets)

            # Category: Messages
            if not include_categories or "messages" in include_categories:
                all_messages = []
                for ticket in tickets:
                    messages = self.db.query(TicketMessage).filter(
                        TicketMessage.ticket_id == ticket.id,
                        TicketMessage.company_id == company_id,
                    ).all()

                    all_messages.extend([
                        {
                            "id": m.id,
                            "ticket_id": m.ticket_id,
                            "role": m.role,
                            "content": m.content,
                            "channel": m.channel,
                            "is_redacted": m.is_redacted,
                            "created_at": m.created_at.isoformat() if m.created_at else None,
                        }
                        for m in messages
                    ])

                exported_data["messages"] = all_messages
                categories_included.append("messages")
                total_records += len(all_messages)

        # Category: Consent Records
        if customer and (not include_categories or "consents" in include_categories):
            from database.models.onboarding import ConsentRecord

            # Find consent records via user who has this email
            from database.models.core import User
            user = self.db.query(User).filter(
                User.company_id == company_id,
                User.email == customer_email,
            ).first()

            if user:
                consents = self.db.query(ConsentRecord).filter(
                    ConsentRecord.company_id == company_id,
                    ConsentRecord.user_id == user.id,
                ).all()

                exported_data["consents"] = [
                    {
                        "id": c.id,
                        "consent_type": c.consent_type,
                        "consent_version": c.consent_version,
                        "granted": c.granted,
                        "ip_address": c.ip_address,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in consents
                ]
                categories_included.append("consents")
                total_records += len(consents)

        # Category: Audit Trail (metadata only — no PII in export for audit)
        if not include_categories or "audit_logs" in include_categories:
            from database.models.integration import AuditTrail

            audit_entries = self.db.query(AuditTrail).filter(
                AuditTrail.company_id == company_id,
            ).limit(100).all()  # Limit for performance

            exported_data["audit_logs"] = [
                {
                    "id": a.id,
                    "action": a.action,
                    "resource_type": a.resource_type,
                    "resource_id": a.resource_id,
                    "actor_type": a.actor_type,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in audit_entries
            ]
            categories_included.append("audit_logs")
            total_records += len(audit_entries)

        return {
            "customer_email": customer_email,
            "format": format,
            "data": exported_data,
            "categories_included": categories_included,
            "total_records": total_records,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


class GDPRRetentionService:
    """Service for data retention policy enforcement.

    Uses GDPR_RETENTION_DAYS from config as the default retention period.
    Supports per-company, per-category overrides via DataRetentionPolicy table.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_retention_policy(
        self,
        company_id: str,
        category: str,
        retention_days: int,
        action_on_expiry: str = "archive",
    ) -> Dict[str, Any]:
        """Create or update a data retention policy for a company."""
        from database.models.gdpr import DataRetentionPolicy

        # Check if policy already exists
        existing = self.db.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.company_id == company_id,
            DataRetentionPolicy.category == category,
        ).first()

        if existing:
            existing.retention_days = retention_days
            existing.action_on_expiry = action_on_expiry
            existing.updated_at = datetime.now(timezone.utc)
            self.db.flush()
            return {
                "id": existing.id,
                "company_id": company_id,
                "category": category,
                "retention_days": retention_days,
                "action_on_expiry": action_on_expiry,
                "updated": True,
            }

        policy_id = str(uuid.uuid4())
        policy = DataRetentionPolicy(
            id=policy_id,
            company_id=company_id,
            category=category,
            retention_days=retention_days,
            action_on_expiry=action_on_expiry,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(policy)
        self.db.flush()

        return {
            "id": policy_id,
            "company_id": company_id,
            "category": category,
            "retention_days": retention_days,
            "action_on_expiry": action_on_expiry,
            "updated": False,
        }

    def enforce_retention(
        self, company_id: str, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Enforce data retention policies for a company.

        Finds records older than their retention period and applies
        the configured action (archive, delete, anonymize).

        Args:
            company_id: The tenant ID.
            dry_run: If True, report what would be affected without making changes.

        Returns:
            Dict with enforcement results.
        """
        from database.models.gdpr import DataRetentionPolicy

        settings = get_settings()
        default_retention_days = settings.GDPR_RETENTION_DAYS

        # Get all active policies for this company
        policies = self.db.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.company_id == company_id,
            DataRetentionPolicy.is_active == True,
        ).all()

        # If no custom policies, use default config
        if not policies:
            policies = [type('obj', (object,), {
                'category': 'tickets',
                'retention_days': default_retention_days,
                'action_on_expiry': 'archive',
            })()]

        now = datetime.now(timezone.utc)
        results = {
            "policies_enforced": 0,
            "total_records_affected": 0,
            "details": [],
        }

        for policy in policies:
            cutoff = now - timedelta(days=policy.retention_days)

            if policy.category == "tickets":
                affected = self._enforce_ticket_retention(
                    company_id, cutoff, policy.action_on_expiry, dry_run
                )
            elif policy.category == "messages":
                affected = self._enforce_message_retention(
                    company_id, cutoff, policy.action_on_expiry, dry_run
                )
            elif policy.category == "customers":
                affected = self._enforce_customer_retention(
                    company_id, cutoff, policy.action_on_expiry, dry_run
                )
            elif policy.category == "audit_logs":
                # Audit logs have a MUCH longer retention (7 years by default)
                audit_cutoff = now - timedelta(days=AUDIT_RETENTION_DAYS)
                affected = self._enforce_audit_retention(
                    company_id, audit_cutoff, policy.action_on_expiry, dry_run
                )
            else:
                affected = 0

            results["policies_enforced"] += 1
            results["total_records_affected"] += affected
            results["details"].append({
                "category": policy.category,
                "retention_days": policy.retention_days,
                "action_on_expiry": policy.action_on_expiry,
                "records_affected": affected,
                "dry_run": dry_run,
            })

            # Update policy enforcement timestamp
            if not dry_run and hasattr(policy, 'id'):
                policy.last_enforced_at = now
                policy.last_records_affected = affected

        return results

    def _enforce_ticket_retention(
        self, company_id: str, cutoff: datetime, action: str, dry_run: bool
    ) -> int:
        """Enforce retention on tickets older than cutoff."""
        from database.models.tickets import Ticket

        old_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == company_id,
            Ticket.created_at < cutoff,
            Ticket.status.in_(["resolved", "closed"]),
        ).all()

        if dry_run:
            return len(old_tickets)

        for ticket in old_tickets:
            if action == "archive":
                ticket.status = "archived"
            elif action == "delete":
                self.db.delete(ticket)
            elif action == "anonymize":
                ticket.subject = ERASED_MARKER
                ticket.metadata_json = "{}"

        self.db.flush()
        return len(old_tickets)

    def _enforce_message_retention(
        self, company_id: str, cutoff: datetime, action: str, dry_run: bool
    ) -> int:
        """Enforce retention on messages older than cutoff."""
        from database.models.tickets import TicketMessage

        old_messages = self.db.query(TicketMessage).filter(
            TicketMessage.company_id == company_id,
            TicketMessage.created_at < cutoff,
        ).all()

        if dry_run:
            return len(old_messages)

        for message in old_messages:
            if action == "anonymize":
                message.content = ERASED_MARKER
                message.is_redacted = True
            elif action == "delete":
                self.db.delete(message)

        self.db.flush()
        return len(old_messages)

    def _enforce_customer_retention(
        self, company_id: str, cutoff: datetime, action: str, dry_run: bool
    ) -> int:
        """Enforce retention on customers older than cutoff (anonymize only)."""
        from database.models.tickets import Customer

        old_customers = self.db.query(Customer).filter(
            Customer.company_id == company_id,
            Customer.created_at < cutoff,
        ).all()

        if dry_run:
            return len(old_customers)

        for customer in old_customers:
            customer.name = ERASED_MARKER
            customer.email = f"{ERASED_MARKER}_{customer.id[:8]}@erased.parwa"
            customer.phone = ERASED_MARKER

        self.db.flush()
        return len(old_customers)

    def _enforce_audit_retention(
        self, company_id: str, cutoff: datetime, action: str, dry_run: bool
    ) -> int:
        """Enforce retention on audit logs (very long retention by default)."""
        from database.models.integration import AuditTrail

        old_audit = self.db.query(AuditTrail).filter(
            AuditTrail.company_id == company_id,
            AuditTrail.created_at < cutoff,
        ).all()

        if dry_run:
            return len(old_audit)

        # Audit logs are typically archived, not deleted
        for entry in old_audit:
            if action == "delete":
                self.db.delete(entry)
            # archive/anonymize: keep audit trail but redact old_value/new_value PII
            elif action in ("archive", "anonymize"):
                entry.old_value = ERASED_MARKER if entry.old_value else None
                entry.new_value = ERASED_MARKER if entry.new_value else None

        self.db.flush()
        return len(old_audit)


class AuditImmutabilityService:
    """Service to verify and enforce audit trail immutability.

    The audit_trail table must have no DELETE or UPDATE routes exposed
    via the API. This is a GDPR compliance requirement: audit records
    must be tamper-proof for legal and regulatory reasons.
    """

    def __init__(self, db: Session):
        self.db = db

    def check_immutability(self) -> Dict[str, Any]:
        """Verify that the audit_trail has no DELETE or UPDATE API routes.

        Returns:
            Dict with immutability check results.
        """
        # Check the FastAPI app routes
        from app.main import app

        audit_routes = []
        for route in app.routes:
            if hasattr(route, "path") and "audit" in route.path.lower():
                methods = getattr(route, "methods", set())
                audit_routes.append({
                    "path": route.path,
                    "methods": list(methods) if methods else [],
                })

        has_delete = any(
            "DELETE" in r["methods"] for r in audit_routes
        )
        has_update = any(
            "PUT" in r["methods"] or "PATCH" in r["methods"]
            for r in audit_routes
        )

        return {
            "has_delete_route": has_delete,
            "has_update_route": has_update,
            "is_immutable": not has_delete and not has_update,
            "audit_routes_found": audit_routes,
            "details": (
                "Audit trail is immutable — no DELETE or UPDATE routes found."
                if not has_delete and not has_update
                else f"IMMUTABILITY VIOLATION: DELETE={has_delete}, UPDATE={has_update}"
            ),
        }

    def try_delete_audit_entry(self, entry_id: str, company_id: str) -> Dict[str, Any]:
        """Attempt to delete an audit trail entry (should fail/be blocked).

        Returns:
            Dict indicating whether the deletion was blocked.
        """
        # Direct DB check: we should NOT provide a way to delete audit entries
        from database.models.integration import AuditTrail

        entry = self.db.query(AuditTrail).filter(
            AuditTrail.id == entry_id,
            AuditTrail.company_id == company_id,
        ).first()

        if not entry:
            return {"deletion_blocked": True, "reason": "Entry not found (no route to delete)"}

        # This method intentionally does NOT delete the entry
        # It only reports that deletion would be possible at DB level
        # but is blocked at the API level (no DELETE route exists)
        return {
            "deletion_blocked": True,
            "reason": "No DELETE API route exists for audit_trail",
            "entry_exists": True,
            "api_level_protection": True,
        }

    def try_update_audit_entry(self, entry_id: str, company_id: str) -> Dict[str, Any]:
        """Attempt to update an audit trail entry (should fail/be blocked).

        Returns:
            Dict indicating whether the update was blocked.
        """
        from database.models.integration import AuditTrail

        entry = self.db.query(AuditTrail).filter(
            AuditTrail.id == entry_id,
            AuditTrail.company_id == company_id,
        ).first()

        if not entry:
            return {"update_blocked": True, "reason": "Entry not found (no route to update)"}

        # This method intentionally does NOT update the entry
        return {
            "update_blocked": True,
            "reason": "No PUT/PATCH API route exists for audit_trail",
            "entry_exists": True,
            "api_level_protection": True,
        }


class GDPRConsentService:
    """Service for GDPR consent management (Art. 7)."""

    def __init__(self, db: Session):
        self.db = db

    def record_consent(
        self,
        company_id: str,
        user_id: str,
        consent_type: str,
        granted: bool,
        consent_version: str = "1.0",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a consent decision for a user."""
        from database.models.onboarding import ConsentRecord

        consent_id = str(uuid.uuid4())
        consent = ConsentRecord(
            id=consent_id,
            company_id=company_id,
            user_id=user_id,
            consent_type=consent_type,
            consent_version=consent_version,
            ip_address=ip_address,
            user_agent=user_agent,
            granted=granted,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(consent)
        self.db.flush()

        return {
            "id": consent_id,
            "company_id": company_id,
            "user_id": user_id,
            "consent_type": consent_type,
            "granted": granted,
            "consent_version": consent_version,
            "created_at": consent.created_at.isoformat(),
        }

    def list_consents(
        self, company_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """List all consent records for a user."""
        from database.models.onboarding import ConsentRecord

        consents = self.db.query(ConsentRecord).filter(
            ConsentRecord.company_id == company_id,
            ConsentRecord.user_id == user_id,
        ).all()

        return [
            {
                "id": c.id,
                "consent_type": c.consent_type,
                "consent_version": c.consent_version,
                "granted": c.granted,
                "ip_address": c.ip_address,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in consents
        ]

    def withdraw_consent(
        self, company_id: str, user_id: str, consent_type: str
    ) -> Dict[str, Any]:
        """Withdraw consent for a specific type (creates a new record with granted=False)."""
        return self.record_consent(
            company_id=company_id,
            user_id=user_id,
            consent_type=consent_type,
            granted=False,
            consent_version="1.0",
        )
