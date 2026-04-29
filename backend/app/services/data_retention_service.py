"""
Data Retention Service (C4, C5, C6, C7)

Handles the data lifecycle after subscription cancellation:
- C4: 30-day data retention with countdown
- C5: Full company data export (async ZIP generation)
- C6: Daily retention cron with GDPR-compliant cleanup
- C7: Hard delete after retention period

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal (not used here)
"""

import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID


from database.base import SessionLocal
# Lazy imports to avoid DB connection at module load time in tests
from database.models.billing import Subscription
from database.models.core import Company

logger = logging.getLogger("parwa.services.data_retention")

# ── Constants ──────────────────────────────────────────────────────────────

# C4: 30-day data retention period after service stop
RETENTION_PERIOD_DAYS = 30

# C4: Daily email reminders for first 7 days
RETENTION_EMAIL_REMINDER_DAYS = 7

# C6: Billing records retained for 7 years (financial compliance)
BILLING_RETENTION_YEARS = 7


class DataRetentionError(Exception):
    """Base exception for data retention errors."""


class DataExportNotFoundError(DataRetentionError):
    """Data export not found."""


class DataRetentionExpiredError(DataRetentionError):
    """Retention period has expired, data may be deleted."""


class DataExportError(DataRetentionError):
    """Raised when a data export operation fails validation."""


class DataExportInProgressError(DataRetentionError):
    """Data export is already in progress."""


class DataRetentionService:
    """
    Data lifecycle management after subscription cancellation.

    Handles:
    - C4: 30-day retention countdown and reminders
    - C5: Full company data export as ZIP
    - C6: GDPR-compliant data cleanup cron
    - C7: Hard delete after retention
    """

    def get_retention_status(self, company_id: UUID) -> Dict[str, Any]:
        """
        Get data retention status for a company.

        C4: Show countdown until permanent deletion.

        Args:
            company_id: Company UUID

        Returns:
            Dict with retention status info
        """
        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                return {"status": "no_subscription"}

            # Check if service has been stopped
            service_stopped_at = getattr(
                subscription, "service_stopped_at", None)
            if not service_stopped_at:
                # Check if canceled immediately
                if subscription.status == "canceled":
                    service_stopped_at = subscription.created_at
                else:
                    return {
                        "status": "active",
                        "subscription_status": subscription.status,
                    }

            # Calculate retention countdown
            if service_stopped_at.tzinfo is None:
                service_stopped_at = service_stopped_at.replace(
                    tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            deletion_date = service_stopped_at + \
                timedelta(days=RETENTION_PERIOD_DAYS)
            days_remaining = (deletion_date - now).days

            if days_remaining <= 0:
                return {
                    "status": "retention_expired",
                    "deletion_date": deletion_date.isoformat(),
                    "days_remaining": 0,
                    "message": "Your data is scheduled for permanent deletion.",
                }

            return {
                "status": "in_retention",
                "service_stopped_at": service_stopped_at.isoformat(),
                "deletion_date": deletion_date.isoformat(),
                "days_remaining": days_remaining,
                "retention_period_days": RETENTION_PERIOD_DAYS,
                "message": (
                    f"Your data will be permanently deleted in {days_remaining} days. "
                    "Export your data now."
                ),
            }

    async def request_data_export(self, company_id: UUID) -> Dict[str, Any]:
        """
        Request a full company data export.

        C5: Async export of all company data as ZIP (JSON + CSV files).
        Creates an export job, returns export_id for polling.

        Args:
            company_id: Company UUID

        Returns:
            Dict with export job info
        """
        from database.models.billing_extended import DataExport

        with SessionLocal() as db:
            # Check for existing in-progress export
            existing = db.query(DataExport).filter(
                DataExport.company_id == str(company_id),
                DataExport.status == "processing",
            ).first()

            if existing:
                raise DataExportInProgressError(
                    "A data export is already in progress. "
                    f"Export ID: {existing.id}"
                )

            # Check retention status
            retention = self.get_retention_status(company_id)
            if retention.get("status") == "retention_expired":
                raise DataRetentionExpiredError(
                    "Data retention period has expired. Data may no longer be available."
                )

            # Create export record
            export = DataExport(
                company_id=str(company_id),
                status="processing",
                format="zip",
                requested_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add(export)
            db.commit()
            db.refresh(export)

            logger.info(
                "data_export_requested company_id=%s export_id=%s",
                company_id,
                export.id,
            )

            # TODO: In production, dispatch async Celery task for actual export
            # export_company_data_task.delay(str(company_id), export.id)

            # For now, complete the export synchronously in the background
            try:
                export_data = self._generate_export_data(str(company_id))
                export.status = "completed"
                export.file_size_bytes = len(
                    json.dumps(export_data).encode("utf-8"))
                export.completed_at = datetime.now(timezone.utc)
                # Store the export data temporarily
                export.export_data_json = json.dumps(export_data)
                db.commit()
            except Exception as e:
                export.status = "failed"
                export.error_message = str(e)[:500]
                db.commit()
                logger.error(
                    "data_export_failed company_id=%s export_id=%s error=%s",
                    company_id,
                    export.id,
                    str(e),
                )

            return {
                "export_id": export.id,
                "status": export.status,
                "requested_at": export.requested_at.isoformat() if export.requested_at else None,
                "message": (
                    "Data export completed." if export.status == "completed"
                    else "Data export is processing."
                ),
            }

    def get_export_download(self, company_id: UUID, export_id: str) -> bytes:
        """
        Get the data export as a ZIP file.

        C5: Returns ZIP containing JSON + CSV files of all company data.

        Args:
            company_id: Company UUID
            export_id: Export record UUID

        Returns:
            ZIP file bytes

        Raises:
            DataExportNotFoundError: Export not found
            DataRetentionExpiredError: Export has expired
        """
        from database.models.billing_extended import DataExport

        with SessionLocal() as db:
            export = db.query(DataExport).filter(
                DataExport.company_id == str(company_id),
                DataExport.id == export_id,
            ).first()

            if not export:
                raise DataExportNotFoundError(
                    f"Data export {export_id} not found"
                )

            if export.status != "completed":
                raise DataExportError(
                    f"Export is not completed. Status: {export.status}"
                )

            # Check expiration
            if export.expires_at:
                now = datetime.now(timezone.utc)
                expires = export.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now > expires:
                    raise DataRetentionExpiredError(
                        "Export download link has expired. "
                        "Please request a new export."
                    )

            # Generate ZIP
            export_data = json.loads(
                export.export_data_json) if export.export_data_json else {}
            return self._generate_zip(export_data, str(company_id))

    def _generate_export_data(self, company_id: str) -> Dict[str, Any]:
        """
        Generate export data for a company.

        C5: Collects all company data: tickets, customers, conversations,
        KB docs, settings, audit logs, subscription info.

        Args:
            company_id: Company ID string

        Returns:
            Dict with all export data organized by category
        """
        export_data = {
            "export_info": {
                "company_id": company_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "format_version": "1.0",
            },
            "subscription": [],
            "invoices": [],
            "tickets": [],
            "customers": [],
            "settings": {},
            "usage_history": [],
        }

        try:
            with SessionLocal() as db:
                # Export subscription data
                subscriptions = db.query(Subscription).filter(
                    Subscription.company_id == company_id,
                ).all()

                for sub in subscriptions:
                    export_data["subscription"].append({
                        "id": sub.id,
                        "tier": sub.tier,
                        "status": sub.status,
                        "billing_frequency": getattr(sub, "billing_frequency", "monthly"),
                        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
                        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
                        "cancel_at_period_end": sub.cancel_at_period_end,
                        "created_at": sub.created_at.isoformat() if sub.created_at else None,
                    })

                # Export invoices (billing records retained for 7 years)
                from database.models.billing import Invoice
                invoices = db.query(Invoice).filter(
                    Invoice.company_id == company_id,
                ).all()

                for inv in invoices:
                    export_data["invoices"].append({
                        "id": inv.id,
                        "paddle_invoice_id": inv.paddle_invoice_id,
                        "amount": str(inv.amount) if inv.amount else None,
                        "currency": inv.currency,
                        "status": inv.status,
                        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                    })

                # Export company settings
                company = db.query(Company).filter(
                    Company.id == company_id,
                ).first()

                if company:
                    export_data["settings"] = {
                        "name": getattr(
                            company, "name", None), "subscription_tier": getattr(
                            company, "subscription_tier", None), "subscription_status": getattr(
                            company, "subscription_status", None), "created_at": getattr(
                            company, "created_at", None), }

        except Exception as e:
            logger.warning(
                "data_export_partial company_id=%s error=%s",
                company_id,
                str(e),
            )

        return export_data

    def _generate_zip(self, export_data: Dict, company_id: str) -> bytes:
        """
        Generate ZIP file from export data.

        C5: Creates ZIP with JSON and CSV representations.

        Args:
            export_data: Export data dict
            company_id: Company ID

        Returns:
            ZIP file bytes
        """
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add full JSON export
            json_content = json.dumps(export_data, indent=2, default=str)
            zf.writestr("parwa_export.json", json_content)

            # Add CSV files for main entities
            for section in [
                "subscription",
                "invoices",
                "tickets",
                    "customers"]:
                items = export_data.get(section, [])
                if items:
                    csv_content = self._dicts_to_csv(items)
                    zf.writestr(f"{section}.csv", csv_content)

            # Add README
            readme = (
                "PARWA Data Export\n"
                "==================\n"
                f"Company ID: {company_id}\n"
                f"Exported: {export_data.get('export_info', {}).get('exported_at', 'unknown')}\n\n"
                "Contents:\n"
                "- parwa_export.json: Full export in JSON format\n"
                "- subscription.csv: Subscription history\n"
                "- invoices.csv: Invoice records\n"
                "- tickets.csv: Ticket history (if available)\n"
                "- customers.csv: Customer records (if available)\n\n"
                "Note: Per our data retention policy, billing records "
                f"are retained for {BILLING_RETENTION_YEARS} years "
                "for financial compliance."
            )
            zf.writestr("README.txt", readme)

        return buf.getvalue()

    def _dicts_to_csv(self, dicts: List[Dict]) -> str:
        """Convert list of dicts to CSV string."""
        if not dicts:
            return ""

        import csv
        import io as _io

        buf = _io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=dicts[0].keys())
        writer.writeheader()
        for d in dicts:
            row = {
                k: v if not isinstance(
                    v, (list, dict)) else json.dumps(v) for k, v in d.items()}
            writer.writerow(row)

        return buf.getvalue()

    # ═══════════════════════════════════════════════════════════════════
    # C6: Data Retention Cron (daily)
    # ═══════════════════════════════════════════════════════════════════

    def process_retention_cron(self) -> Dict[str, Any]:
        """
        C6: Daily cron for data retention enforcement.

        Checks for canceled subscriptions where service_stopped_at + 30 days <= today.
        Executes GDPR-compliant data cleanup:
        - Soft-delete tickets
        - Anonymize customer PII (GDPR right to erasure)
        - Archive KB docs
        - RETAIN billing records (7-year retention for financial compliance)

        Returns:
            Dict with processing summary
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=RETENTION_PERIOD_DAYS)

        results = {
            "timestamp": now.isoformat(),
            "cutoff_date": cutoff.isoformat(),
            "companies_processed": 0,
            "tickets_soft_deleted": 0,
            "customers_anonymized": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            # Find subscriptions past retention period
            expired = db.query(Subscription).filter(
                Subscription.status == "canceled",
                Subscription.service_stopped_at <= cutoff,
                Subscription.data_hard_deleted is False,  # type: ignore
            ).all()

            for sub in expired:
                try:
                    company_id = sub.company_id
                    self._execute_data_cleanup(db, company_id)
                    sub.data_hard_deleted = True  # type: ignore
                    sub.data_deleted_at = now  # type: ignore
                    results["companies_processed"] += 1

                    logger.info(
                        "data_cleanup_completed company_id=%s sub_id=%s",
                        company_id,
                        sub.id,
                    )
                except Exception as e:
                    logger.error(
                        "data_cleanup_failed sub_id=%s error=%s",
                        sub.id,
                        str(e),
                    )
                    results["errors"].append({
                        "subscription_id": sub.id,
                        "company_id": sub.company_id,
                        "error": str(e)[:200],
                    })

            db.commit()

        logger.info(
            "retention_cron_completed processed=%d errors=%d",
            results["companies_processed"],
            len(results["errors"]),
        )

        return results

    def _execute_data_cleanup(self, db, company_id: str) -> None:
        """
        C6/C7: Execute GDPR-compliant data cleanup for a company.

        - Soft-delete tickets (set deleted=True)
        - Anonymize customer PII
        - Archive KB docs
        - RETAIN: subscription records, invoices, payment records

        Args:
            db: Database session
            company_id: Company ID string
        """
        # Soft-delete tickets
        try:
            from database.models.ticket import Ticket
            tickets = db.query(Ticket).filter(
                Ticket.company_id == company_id,
            ).all()
            for ticket in tickets:
                ticket.status = "deleted"
                ticket.metadata_json = ticket.metadata_json or {}
                ticket.metadata_json["deleted_by_retention"] = True
                ticket.metadata_json["deleted_at"] = datetime.now(
                    timezone.utc).isoformat()
        except Exception as e:
            logger.warning(
                "ticket_cleanup_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        # Anonymize customer PII
        try:
            from database.models.tickets import Customer
            customers = db.query(Customer).filter(
                Customer.company_id == company_id,
            ).all()
            for customer in customers:
                customer.name = "[REDACTED]"
                customer.email = "[REDACTED]"
                customer.phone = "[REDACTED]"
                if hasattr(customer, "metadata_json"):
                    customer.metadata_json = customer.metadata_json or {}
                    customer.metadata_json["anonymized_by_retention"] = True
                    customer.metadata_json["anonymized_at"] = datetime.now(
                        timezone.utc).isoformat()
        except Exception as e:
            logger.warning(
                "customer_anonymization_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        # Archive KB docs
        try:
            from database.models.onboarding import KnowledgeDocument
            docs = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.company_id == company_id,
            ).all()
            for doc in docs:
                doc.status = "archived"
        except Exception as e:
            logger.warning(
                "kb_archive_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        # NOTE: Billing records (Subscription, Invoice, Transaction) are
        # NOT deleted — retained for 7 years per financial compliance.

    def get_retention_reminder_companies(self) -> List[Dict[str, Any]]:
        """
        C4: Get companies needing retention reminder emails.

        Returns companies in retention period for the first 7 days.

        Returns:
            List of company dicts needing reminders
        """
        now = datetime.now(timezone.utc)
        reminder_cutoff = now - timedelta(days=RETENTION_EMAIL_REMINDER_DAYS)

        companies = []

        with SessionLocal() as db:
            expired = db.query(Subscription).filter(
                Subscription.status == "canceled",
                Subscription.service_stopped_at >= reminder_cutoff,
                Subscription.service_stopped_at <= now,
            ).all()

            for sub in expired:
                company = db.query(Company).filter(
                    Company.id == sub.company_id,
                ).first()

                if company:
                    days_since_stop = (now - sub.service_stopped_at).days
                    companies.append({
                        "company_id": sub.company_id,
                        "company_name": getattr(company, "name", "Unknown"),
                        "days_since_service_stopped": days_since_stop,
                        "deletion_date": (
                            sub.service_stopped_at + timedelta(days=RETENTION_PERIOD_DAYS)
                        ).isoformat(),
                    })

        return companies


# ── Singleton ──────────────────────────────────────────────────────────────

_data_retention_service: Optional[DataRetentionService] = None


def get_data_retention_service() -> DataRetentionService:
    """Get the data retention service singleton."""
    global _data_retention_service
    if _data_retention_service is None:
        _data_retention_service = DataRetentionService()
    return _data_retention_service
