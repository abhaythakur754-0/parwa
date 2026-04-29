"""
Financial Safety Service (Day 5: FS1-FS3)

Protects PARWA from revenue loss:
- FS1: Maximum overage cap ($500/month global hard limit)
- FS2: Anomaly detection (ticket volume spike detection)
- FS3: Invoice audit (weekly reconciliation with Paddle)

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing import Invoice, Subscription
from database.models.billing_extended import UsageRecord
from database.models.core import Company

logger = logging.getLogger("parwa.services.financial_safety")

# ── Constants ─────────────────────────────────────────────────────────────

# FS1: Global maximum overage per company per month ($500)
GLOBAL_OVERAGE_MAX: Decimal = Decimal("500.00")

# FS2: Ticket volume spike multiplier (3x yesterday = anomaly)
ANOMALY_DETECTION_MULTIPLIER: float = 3.0

# FS2: Minimum yesterday volume to trigger anomaly check
# Don't flag if yesterday < 100 tickets (too noisy for small volumes)
ANOMALY_MIN_VOLUME: int = 100


# ── Exception Classes ─────────────────────────────────────────────────────


class FinancialSafetyError(Exception):
    """Base exception for financial safety errors."""


class GlobalCapExceededError(FinancialSafetyError):
    """Raised when the global overage cap is exceeded."""


class AnomalyDetectedError(FinancialSafetyError):
    """Raised when a spending anomaly is detected."""


class InvoiceAuditError(FinancialSafetyError):
    """Raised when an invoice audit fails."""


# ── Service Implementation ───────────────────────────────────────────────


class FinancialSafetyService:
    """
    Financial safety service for PARWA SaaS billing.

    Provides:
    - Global overage cap enforcement ($500/month hard limit)
    - Anomaly detection (ticket volume spike monitoring)
    - Invoice audit (weekly reconciliation with Paddle)

    Usage:
        service = FinancialSafetyService()

        # Enforce global cap before overage
        result = service.enforce_global_overage_cap(company_id, current_overage=Decimal("450.00"))

        # Check for anomalies
        anomaly = service.check_anomaly(company_id)

        # Run weekly invoice audit
        audit = service.audit_invoices(company_id)
    """

    def __init__(self) -> None:
        """Initialize the financial safety service."""

    # ── Validation Helpers ───────────────────────────────────────────────

    @staticmethod
    def _validate_company_id(company_id: Any) -> str:
        """
        Validate and normalize company_id.

        BC-001: All operations validate company_id.
        Accepts UUID or str, returns string representation.

        Args:
            company_id: Company identifier (UUID or str)

        Returns:
            String representation of the company_id

        Raises:
            FinancialSafetyError: If company_id is invalid
        """
        if company_id is None:
            raise FinancialSafetyError("company_id is required")

        if isinstance(company_id, UUID):
            return str(company_id)

        if isinstance(company_id, str):
            company_id = company_id.strip()
            if not company_id:
                raise FinancialSafetyError("company_id cannot be empty")
            return company_id

        raise FinancialSafetyError(
            f"Invalid company_id type: {type(company_id).__name__}. "
            "Expected UUID or str."
        )

    @staticmethod
    def _round_money(amount: Decimal) -> Decimal:
        """
        Round a Decimal amount to 2 decimal places (currency precision).

        BC-002: All money calculations use Decimal.

        Args:
            amount: Decimal amount to round

        Returns:
            Rounded Decimal with 2 decimal places
        """
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _get_current_month_overage(
        self,
        db: Session,
        company_id: str,
    ) -> Decimal:
        """
        Calculate current period's overage charges for a company.

        Sums overage_charges from all daily UsageRecords for the
        current calendar month.

        Args:
            db: Database session
            company_id: Company ID string

        Returns:
            Total overage charges as Decimal (BC-002)
        """
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")

        total = (
            db.query(
                func.coalesce(func.sum(UsageRecord.overage_charges), Decimal("0.00"))
            )
            .filter(
                UsageRecord.company_id == company_id,
                UsageRecord.record_month == current_month,
            )
            .scalar()
        )

        return Decimal(str(total or 0))

    # ── FS1: Global Overage Cap ──────────────────────────────────────────

    def enforce_global_overage_cap(
        self,
        company_id: Any,
        current_overage_amount: Any,
    ) -> Dict[str, Any]:
        """
        Enforce the global maximum overage cap ($500/month). (FS1)

        This is a PARWA-level hard limit that applies regardless of
        any customer-configured spending cap. No company can be charged
        more than $500 in overage in a single billing month.

        If current >= $500: deny any further overage charges.
        Otherwise: allow with remaining balance info.

        Args:
            company_id: Company UUID or str
            current_overage_amount: Current overage amount (Decimal/str/float)

        Returns:
            Dict with:
                - allowed (bool): Whether further charges are allowed
                - remaining (Decimal): Remaining before global cap
                - message (str): Status description
                - current_overage (Decimal): Current period overage
                - global_max (Decimal): The global cap ($500)

        Raises:
            FinancialSafetyError: If company_id or amount is invalid
        """
        company_id_str = self._validate_company_id(company_id)

        # BC-002: Convert to Decimal
        try:
            overage_decimal = Decimal(str(current_overage_amount))
        except Exception:
            raise FinancialSafetyError(
                f"Invalid current_overage_amount: {current_overage_amount}"
            )

        if overage_decimal < Decimal("0"):
            raise FinancialSafetyError("current_overage_amount must be non-negative")

        remaining = GLOBAL_OVERAGE_MAX - overage_decimal

        if overage_decimal >= GLOBAL_OVERAGE_MAX:
            logger.warning(
                "global_overage_cap_exceeded " "company_id=%s current=%s max=%s",
                company_id_str,
                overage_decimal,
                GLOBAL_OVERAGE_MAX,
            )
            return {
                "allowed": False,
                "remaining": Decimal("0.00"),
                "message": (
                    f"Global overage maximum (${GLOBAL_OVERAGE_MAX}) reached. "
                    "No further overage charges allowed this period."
                ),
                "current_overage": str(overage_decimal),
                "global_max": str(GLOBAL_OVERAGE_MAX),
            }

        logger.info(
            "global_overage_cap_check_passed " "company_id=%s current=%s remaining=%s",
            company_id_str,
            overage_decimal,
            self._round_money(remaining),
        )

        return {
            "allowed": True,
            "remaining": str(self._round_money(remaining)),
            "message": "Within global overage cap.",
            "current_overage": str(overage_decimal),
            "global_max": str(GLOBAL_OVERAGE_MAX),
        }

    # ── FS2: Anomaly Detection ───────────────────────────────────────────

    def check_anomaly(
        self,
        company_id: Any,
    ) -> Dict[str, Any]:
        """
        Check for ticket volume anomalies for a company. (FS2)

        Compares today's ticket volume against yesterday's. If today's
        volume exceeds ANOMALY_DETECTION_MULTIPLIER (3x) times yesterday's,
        and yesterday's volume is >= ANOMALY_MIN_VOLUME (100 tickets),
        the spike is flagged as an anomaly.

        Args:
            company_id: Company UUID or str

        Returns:
            Dict with:
                - anomaly_detected (bool): Whether anomaly was found
                - today_count (int): Today's ticket count
                - yesterday_count (int): Yesterday's ticket count
                - ratio (float): today_count / yesterday_count
                - severity (str): "none", "low", "medium", "high"
                - message (str): Description
        """
        company_id_str = self._validate_company_id(company_id)

        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)

        with SessionLocal() as db:
            # Get today's ticket count
            today_record = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.company_id == company_id_str,
                    UsageRecord.record_date == today,
                )
                .first()
            )
            today_count = today_record.tickets_used if today_record else 0

            # Get yesterday's ticket count
            yesterday_record = (
                db.query(UsageRecord)
                .filter(
                    UsageRecord.company_id == company_id_str,
                    UsageRecord.record_date == yesterday,
                )
                .first()
            )
            yesterday_count = yesterday_record.tickets_used if yesterday_record else 0

            # Calculate ratio
            if yesterday_count > 0:
                ratio = today_count / yesterday_count
            else:
                ratio = float("inf") if today_count > 0 else 0.0

            # Determine anomaly status
            anomaly_detected = False
            severity = "none"
            message = "No anomaly detected."

            # Only check if yesterday had meaningful volume
            if yesterday_count >= ANOMALY_MIN_VOLUME:
                if ratio >= ANOMALY_DETECTION_MULTIPLIER:
                    anomaly_detected = True
                    message = (
                        f"Anomaly: Today's ticket volume ({today_count}) is "
                        f"{ratio:.1f}x yesterday's ({yesterday_count}). "
                        "Possible abuse or misconfiguration."
                    )

                    # Severity classification
                    if ratio >= 10.0:
                        severity = "high"
                    elif ratio >= 5.0:
                        severity = "medium"
                    else:
                        severity = "low"

                    logger.warning(
                        "anomaly_detected company_id=%s "
                        "today=%d yesterday=%d ratio=%.1f severity=%s",
                        company_id_str,
                        today_count,
                        yesterday_count,
                        ratio,
                        severity,
                    )
            elif today_count > 0 and yesterday_count == 0:
                # First day of activity or reset — not necessarily anomalous
                logger.info(
                    "anomaly_check_skip_no_baseline company_id=%s today=%d",
                    company_id_str,
                    today_count,
                )

            logger.info(
                "anomaly_check company_id=%s today=%d yesterday=%d "
                "ratio=%.1f detected=%s severity=%s",
                company_id_str,
                today_count,
                yesterday_count,
                ratio,
                anomaly_detected,
                severity,
            )

            return {
                "company_id": company_id_str,
                "anomaly_detected": anomaly_detected,
                "today_count": today_count,
                "yesterday_count": yesterday_count,
                "ratio": round(ratio, 2) if ratio != float("inf") else -1.0,
                "severity": severity,
                "message": message,
            }

    # ── FS2: Daily Anomaly Check ─────────────────────────────────────────

    def run_daily_anomaly_check(self) -> Dict[str, Any]:
        """
        Run anomaly detection for all active companies. (FS2)

        Intended to be called by a daily cron job. Iterates over all
        companies with active subscriptions and runs check_anomaly
        for each.

        Returns:
            Dict with:
                - companies_checked (int): Total companies scanned
                - anomalies_found (int): Companies with anomalies
                - anomalies (List[Dict]): Details of detected anomalies
                - checked_at (str): Timestamp of the check
        """
        results: Dict[str, Any] = {
            "companies_checked": 0,
            "anomalies_found": 0,
            "anomalies": [],
            "errors": [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        with SessionLocal() as db:
            # Get all active companies
            companies = (
                db.query(Company)
                .join(
                    Subscription,
                    Company.id == Subscription.company_id,
                )
                .filter(Subscription.status == "active")
                .all()
            )

            results["companies_checked"] = len(companies)

            for company in companies:
                try:
                    anomaly = self.check_anomaly(str(company.id))

                    if anomaly["anomaly_detected"]:
                        results["anomalies_found"] += 1
                        results["anomalies"].append(
                            {
                                "company_id": str(company.id),
                                "company_name": company.name,
                                "today_count": anomaly["today_count"],
                                "yesterday_count": anomaly["yesterday_count"],
                                "ratio": anomaly["ratio"],
                                "severity": anomaly["severity"],
                            }
                        )

                        # Emit alert event
                        try:
                            import asyncio

                            from app.core.event_emitter import emit_billing_event

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(
                                    emit_billing_event(
                                        company_id=str(company.id),
                                        event_type="anomaly_detected",
                                        data=anomaly,
                                    )
                                )
                            finally:
                                loop.close()
                        except Exception:
                            # Non-critical: don't fail the check
                            pass

                except Exception as exc:
                    results["errors"].append(
                        {
                            "company_id": str(company.id),
                            "error": str(exc)[:200],
                        }
                    )
                    logger.error(
                        "daily_anomaly_check_error company_id=%s error=%s",
                        company.id,
                        str(exc)[:200],
                    )

        logger.info(
            "daily_anomaly_check_completed checked=%d anomalies=%d errors=%d",
            results["companies_checked"],
            results["anomalies_found"],
            len(results["errors"]),
        )

        return results

    # ── FS3: Invoice Audit ───────────────────────────────────────────────

    def audit_invoices(
        self,
        company_id: Any,
    ) -> Dict[str, Any]:
        """
        Audit local invoices against Paddle invoices. (FS3)

        Compares local invoice records with Paddle's invoice records
        to detect discrepancies such as:
        - Mismatched amounts
        - Missing local records (Paddle has them, we don't)
        - Missing Paddle records (we have them, Paddle doesn't)

        Args:
            company_id: Company UUID or str

        Returns:
            Dict with:
                - matched (int): Invoices that match
                - mismatched (int): Invoices with amount discrepancies
                - missing_local (int): Paddle invoices not in local DB
                - missing_paddle (int): Local invoices not in Paddle
                - details (List[Dict]): Per-invoice reconciliation details
        """
        company_id_str = self._validate_company_id(company_id)

        results: Dict[str, Any] = {
            "company_id": company_id_str,
            "matched": 0,
            "mismatched": 0,
            "missing_local": 0,
            "missing_paddle": 0,
            "details": [],
            "errors": [],
        }

        try:
            # Fetch Paddle invoices
            paddle_invoices = self._fetch_paddle_invoices(company_id_str)
        except Exception as exc:
            results["errors"].append(
                {
                    "source": "paddle_fetch",
                    "error": str(exc)[:200],
                }
            )
            logger.error(
                "invoice_audit_paddle_fetch_failed company_id=%s error=%s",
                company_id_str,
                str(exc),
            )
            return results

        with SessionLocal() as db:
            # Get local invoices
            local_invoices = (
                db.query(Invoice).filter(Invoice.company_id == company_id_str).all()
            )

            # Build lookup maps by paddle_invoice_id
            local_map: Dict[str, Invoice] = {}
            for inv in local_invoices:
                if inv.paddle_invoice_id:
                    local_map[inv.paddle_invoice_id] = inv

            paddle_map: Dict[str, Dict[str, Any]] = {}
            for paddle_inv in paddle_invoices:
                paddle_id = paddle_inv.get("id")
                if paddle_id:
                    paddle_map[paddle_id] = paddle_inv

            # Compare
            all_invoice_ids = set(local_map.keys()) | set(paddle_map.keys())

            for inv_id in all_invoice_ids:
                try:
                    local = local_map.get(inv_id)
                    paddle = paddle_map.get(inv_id)

                    if local and paddle:
                        # Both exist — compare amounts
                        paddle_amount = Decimal(
                            str(paddle.get("total", paddle.get("amount", "0")))
                        )

                        if self._round_money(local.amount) == self._round_money(
                            paddle_amount
                        ):
                            results["matched"] += 1
                        else:
                            results["mismatched"] += 1
                            results["details"].append(
                                {
                                    "invoice_id": inv_id,
                                    "issue": "amount_mismatch",
                                    "local_amount": str(local.amount),
                                    "paddle_amount": str(paddle_amount),
                                    "local_status": local.status,
                                }
                            )

                            logger.warning(
                                "invoice_mismatch company_id=%s inv_id=%s "
                                "local=%s paddle=%s",
                                company_id_str,
                                inv_id,
                                local.amount,
                                paddle_amount,
                            )

                    elif paddle and not local:
                        # Paddle has it, we don't
                        results["missing_local"] += 1
                        results["details"].append(
                            {
                                "invoice_id": inv_id,
                                "issue": "missing_local",
                                "paddle_amount": str(
                                    paddle.get("total", paddle.get("amount", "0"))
                                ),
                                "paddle_status": paddle.get("status"),
                            }
                        )

                        logger.warning(
                            "invoice_missing_local company_id=%s inv_id=%s",
                            company_id_str,
                            inv_id,
                        )

                    elif local and not paddle:
                        # We have it, Paddle doesn't
                        results["missing_paddle"] += 1
                        results["details"].append(
                            {
                                "invoice_id": inv_id,
                                "issue": "missing_paddle",
                                "local_amount": str(local.amount),
                                "local_status": local.status,
                            }
                        )

                        logger.warning(
                            "invoice_missing_paddle company_id=%s inv_id=%s",
                            company_id_str,
                            inv_id,
                        )

                except Exception as exc:
                    results["errors"].append(
                        {
                            "invoice_id": inv_id,
                            "error": str(exc)[:200],
                        }
                    )

        logger.info(
            "invoice_audit_completed company_id=%s "
            "matched=%d mismatched=%d missing_local=%d missing_paddle=%d",
            company_id_str,
            results["matched"],
            results["mismatched"],
            results["missing_local"],
            results["missing_paddle"],
        )

        return results

    def _fetch_paddle_invoices(
        self,
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch invoices from Paddle API for a company.

        Uses the Paddle client to get the invoice list.
        Falls back to empty list on failure.

        Args:
            company_id: Company ID string

        Returns:
            List of invoice dicts from Paddle
        """
        try:
            import asyncio

            from app.clients.paddle_client import get_paddle_client

            with SessionLocal() as db:
                company = db.query(Company).filter(Company.id == company_id).first()

                if not company or not company.paddle_customer_id:
                    logger.info(
                        "invoice_audit_skip_no_paddle company_id=%s",
                        company_id,
                    )
                    return []

                paddle = get_paddle_client()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        paddle.get_invoices(customer_id=company.paddle_customer_id)
                    )
                finally:
                    loop.close()

                return result.get("data", [])

        except Exception as exc:
            logger.warning(
                "paddle_invoice_fetch_failed company_id=%s error=%s",
                company_id,
                str(exc)[:200],
            )
            return []

    # ── FS3: Weekly Invoice Audit ────────────────────────────────────────

    def run_weekly_invoice_audit(self) -> Dict[str, Any]:
        """
        Run invoice audit for all active companies. (FS3)

        Intended to be called by a weekly cron job. For each company:
        1. Runs audit_invoices
        2. Auto-syncs matching invoices
        3. Alerts on mismatches

        Returns:
            Dict with:
                - companies_audited (int): Total companies checked
                - total_matched (int): Total matching invoices
                - total_mismatched (int): Total mismatched invoices
                - companies_with_issues (int): Companies with discrepancies
                - issues (List[Dict]): Companies needing attention
                - errors (List[Dict]): Processing errors
        """
        results: Dict[str, Any] = {
            "companies_audited": 0,
            "total_matched": 0,
            "total_mismatched": 0,
            "total_missing_local": 0,
            "total_missing_paddle": 0,
            "companies_with_issues": 0,
            "issues": [],
            "errors": [],
            "audited_at": datetime.now(timezone.utc).isoformat(),
        }

        with SessionLocal() as db:
            # Get all active companies with Paddle customer IDs
            companies = (
                db.query(Company).filter(Company.paddle_customer_id.isnot(None)).all()
            )

            results["companies_audited"] = len(companies)

            for company in companies:
                try:
                    audit = self.audit_invoices(str(company.id))

                    results["total_matched"] += audit["matched"]
                    results["total_mismatched"] += audit["mismatched"]
                    results["total_missing_local"] += audit["missing_local"]
                    results["total_missing_paddle"] += audit["missing_paddle"]

                    has_issues = (
                        audit["mismatched"] > 0
                        or audit["missing_local"] > 0
                        or audit["missing_paddle"] > 0
                    )

                    if has_issues:
                        results["companies_with_issues"] += 1
                        results["issues"].append(
                            {
                                "company_id": str(company.id),
                                "company_name": company.name,
                                "mismatched": audit["mismatched"],
                                "missing_local": audit["missing_local"],
                                "missing_paddle": audit["missing_paddle"],
                            }
                        )

                        # Attempt auto-sync for missing local invoices
                        if audit["missing_local"] > 0:
                            self._auto_sync_missing_invoices(
                                str(company.id), audit["details"]
                            )

                        # Emit alert
                        try:
                            import asyncio

                            from app.core.event_emitter import emit_billing_event

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(
                                    emit_billing_event(
                                        company_id=str(company.id),
                                        event_type="invoice_audit_issue",
                                        data={
                                            "mismatched": audit["mismatched"],
                                            "missing_local": audit["missing_local"],
                                            "missing_paddle": audit["missing_paddle"],
                                        },
                                    )
                                )
                            finally:
                                loop.close()
                        except Exception:
                            pass

                except Exception as exc:
                    results["errors"].append(
                        {
                            "company_id": str(company.id),
                            "error": str(exc)[:200],
                        }
                    )
                    logger.error(
                        "weekly_audit_error company_id=%s error=%s",
                        company.id,
                        str(exc)[:200],
                    )

        logger.info(
            "weekly_invoice_audit_completed audited=%d "
            "matched=%d mismatched=%d missing_local=%d missing_paddle=%d "
            "issues=%d errors=%d",
            results["companies_audited"],
            results["total_matched"],
            results["total_mismatched"],
            results["total_missing_local"],
            results["total_missing_paddle"],
            results["companies_with_issues"],
            len(results["errors"]),
        )

        return results

    def _auto_sync_missing_invoices(
        self,
        company_id: str,
        details: List[Dict[str, Any]],
    ) -> int:
        """
        Auto-sync invoices that exist in Paddle but not locally.

        Creates local Invoice records for any invoices marked as
        "missing_local" in the audit details.

        Args:
            company_id: Company ID string
            details: Audit details list from audit_invoices

        Returns:
            Number of invoices synced
        """
        synced = 0

        with SessionLocal() as db:
            for detail in details:
                if detail.get("issue") != "missing_local":
                    continue

                invoice_id = detail.get("invoice_id")
                if not invoice_id:
                    continue

                # Check not already created (race condition guard)
                existing = (
                    db.query(Invoice)
                    .filter(
                        Invoice.paddle_invoice_id == invoice_id,
                    )
                    .first()
                )
                if existing:
                    continue

                try:
                    amount = Decimal(str(detail.get("paddle_amount", "0")))
                    status = detail.get("paddle_status", "draft")

                    invoice = Invoice(
                        company_id=company_id,
                        paddle_invoice_id=invoice_id,
                        amount=amount,
                        currency="USD",
                        status=status,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(invoice)
                    synced += 1

                except Exception as exc:
                    logger.error(
                        "auto_sync_invoice_failed company_id=%s inv_id=%s error=%s",
                        company_id,
                        invoice_id,
                        str(exc)[:200],
                    )

            if synced > 0:
                db.commit()

        logger.info(
            "auto_sync_invoices company_id=%s synced=%d",
            company_id,
            synced,
        )

        return synced


# ── Singleton Service ────────────────────────────────────────────────────

_financial_safety_service: Optional[FinancialSafetyService] = None


def get_financial_safety_service() -> FinancialSafetyService:
    """
    Get the financial safety service singleton.

    Returns:
        Shared FinancialSafetyService instance
    """
    global _financial_safety_service
    if _financial_safety_service is None:
        _financial_safety_service = FinancialSafetyService()
    return _financial_safety_service
