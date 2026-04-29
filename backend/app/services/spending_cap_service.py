"""
Spending Cap Service (Day 5: SC1-SC4)

Customer-configurable spending caps for overage charges:
- SC1: Customer sets max overage per period
- SC2: Hard cap enforcement — block new tickets when cap reached
- SC3: Soft cap alerts at configurable thresholds (50%, 75%, 90%)
- SC4: No-cap option (default unlimited)

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing_extended import UsageRecord

logger = logging.getLogger("parwa.services.spending_cap")

# Default soft-cap alert thresholds (percentages)
DEFAULT_THRESHOLDS: List[int] = [50, 75, 90]

# FS1: Global hard cap — no customer cap can exceed this
GLOBAL_MAX_OVERAGE: Decimal = Decimal("500.00")

# Minimum allowed cap (guard rail)
MIN_CAP_AMOUNT: Decimal = Decimal("1.00")


# ── Exception Classes ─────────────────────────────────────────────────────

class SpendingCapError(Exception):
    """Base exception for spending cap errors."""


class SpendingCapExceededError(SpendingCapError):
    """Raised when the spending cap has been reached."""


# ── Spending Cap ORM stub ────────────────────────────────────────────────
# The SpendingCap model is being added in parallel via migration.
# We define it here so the service is self-contained and importable even
# before the migration runs.  The model is intentionally lightweight.
#
# Columns: company_id, max_overage_amount, alert_thresholds, is_active,
#           created_at, updated_at
# The migration file will create the actual table.

class _SpendingCapModel:
    """Lightweight stub describing the SpendingCap table schema.

    Actual SQLAlchemy model is created via Alembic migration.
    This allows the service to be imported and tested before migration.
    """
    __tablename__ = "spending_caps"

    # Column stubs (populated at import time from DB if table exists)


# ── Service Implementation ───────────────────────────────────────────────

class SpendingCapService:
    """
    Spending Cap service for PARWA SaaS billing.

    Manages customer-configurable overage spending caps with:
    - Hard cap enforcement (block tickets when limit reached)
    - Soft cap alerts (configurable percentage thresholds)
    - No-cap option (unlimited overage)

    Usage:
        service = SpendingCapService()

        # Set a cap
        service.set_spending_cap(company_id, max_overage_amount=Decimal("50.00"))

        # Check before processing a new ticket
        result = service.check_cap_before_overage(company_id, proposed_charge=Decimal("0.10"))

        # Check soft cap alerts
        alerts = service.check_soft_cap_alerts(company_id, current_overage=Decimal("30.00"))
    """

    def __init__(self) -> None:
        """Initialize the spending cap service."""
        self._table_available: Optional[bool] = None

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
            SpendingCapError: If company_id is invalid
        """
        if company_id is None:
            raise SpendingCapError("company_id is required")

        if isinstance(company_id, UUID):
            return str(company_id)

        if isinstance(company_id, str):
            company_id = company_id.strip()
            if not company_id:
                raise SpendingCapError("company_id cannot be empty")
            return company_id

        raise SpendingCapError(
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

    def _get_or_create_cap_table(self, db: Session):
        """
        Return the SpendingCap ORM class, importing lazily.

        If the spending_caps table does not exist yet (migration not run),
        returns None and logs a warning.

        Args:
            db: Database session (used for table inspection)

        Returns:
            SpendingCap model class or None
        """
        if self._table_available is False:
            return None

        try:
            # Attempt to import — will succeed once migration runs
            from database.models.billing_extended import SpendingCap  # type: ignore
            self._table_available = True
            return SpendingCap
        except ImportError:
            self._table_available = False
            logger.warning(
                "spending_caps table not available — "
                "SpendingCap model not found in billing_extended. "
                "Ensure migration has been run."
            )
            return None

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
                func.coalesce(
                    func.sum(
                        UsageRecord.overage_charges),
                    Decimal("0.00"))) .filter(
                UsageRecord.company_id == company_id,
                UsageRecord.record_month == current_month,
            ) .scalar())

        return Decimal(str(total or 0))

    # ── Public API: SC1 ──────────────────────────────────────────────────

    def set_spending_cap(
        self,
        company_id: Any,
        max_overage_amount: Optional[Any] = None,
        alert_thresholds: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Set or update a spending cap for a company. (SC1)

        If max_overage_amount is None, this means "no cap" — the cap
        record is deleted and the company operates in unlimited mode (SC4).

        The customer must acknowledge that AI will stop accepting tickets
        when the hard limit is reached.

        Args:
            company_id: Company UUID or str
            max_overage_amount: Maximum overage in USD (Decimal/str/float),
                or None for no cap (SC4)
            alert_thresholds: List of percentage thresholds for soft alerts,
                e.g. [50, 75, 90]. Defaults to [50, 75, 90].

        Returns:
            Dict with:
                - company_id, max_overage_amount (or null for no cap),
                  alert_thresholds, acknowledgment_required, is_active

        Raises:
            SpendingCapError: If company_id invalid or cap amount invalid
        """
        company_id_str = self._validate_company_id(company_id)

        # SC4: None means "no cap" — remove any existing cap
        if max_overage_amount is None:
            self.remove_spending_cap(company_id_str)
            logger.info(
                "spending_cap_removed_no_cap "
                "company_id=%s reason=explicit_none",
                company_id_str,
            )
            return {
                "company_id": company_id_str,
                "max_overage_amount": None,
                "alert_thresholds": [],
                "is_active": False,
                "acknowledgment_required": False,
                "message": "No spending cap set. Overage is unlimited.",
            }

        # BC-002: Convert to Decimal immediately
        try:
            cap_decimal = Decimal(str(max_overage_amount))
        except Exception:
            raise SpendingCapError(
                f"Invalid max_overage_amount: {max_overage_amount}. "
                "Must be a numeric value."
            )

        if cap_decimal < Decimal("0"):
            raise SpendingCapError(
                "max_overage_amount must be non-negative"
            )

        # FS1: Enforce global maximum
        if cap_decimal > GLOBAL_MAX_OVERAGE:
            cap_decimal = GLOBAL_MAX_OVERAGE
            logger.info(
                "spending_cap_clamped_to_global_max "
                "company_id=%s requested=%s clamped=%s",
                company_id_str,
                max_overage_amount,
                GLOBAL_MAX_OVERAGE,
            )

        cap_decimal = self._round_money(cap_decimal)

        # Default thresholds
        thresholds = alert_thresholds or DEFAULT_THRESHOLDS
        if not isinstance(thresholds, list):
            thresholds = DEFAULT_THRESHOLDS

        thresholds = sorted(set(
            t for t in thresholds if isinstance(t, int) and 0 < t <= 100
        ))

        with SessionLocal() as db:
            SpendingCap = self._get_or_create_cap_table(db)
            if SpendingCap is None:
                # Table not available — return simulated result
                logger.warning(
                    "spending_cap_set_table_unavailable company_id=%s cap=%s",
                    company_id_str,
                    cap_decimal,
                )
                return {
                    "company_id": company_id_str,
                    "max_overage_amount": str(cap_decimal),
                    "alert_thresholds": thresholds,
                    "is_active": True,
                    "acknowledgment_required": True,
                    "message": (
                        "Spending cap recorded (pending migration). "
                        "AI stops accepting tickets when limit reached."
                    ),
                }

            # Upsert: find existing or create new
            existing = (
                db.query(SpendingCap)
                .filter(SpendingCap.company_id == company_id_str)
                .first()
            )

            if existing:
                existing.max_overage_amount = cap_decimal
                existing.alert_thresholds = json.dumps(thresholds)
                existing.is_active = True
                existing.updated_at = datetime.now(timezone.utc)
            else:
                cap_record = SpendingCap(
                    id=str(uuid.uuid4()),
                    company_id=company_id_str,
                    max_overage_amount=cap_decimal,
                    alert_thresholds=json.dumps(thresholds),
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(cap_record)

            db.commit()

            logger.info(
                "spending_cap_set "
                "company_id=%s cap=%s thresholds=%s",
                company_id_str,
                cap_decimal,
                thresholds,
            )

            return {
                "company_id": company_id_str,
                "max_overage_amount": str(cap_decimal),
                "alert_thresholds": thresholds,
                "is_active": True,
                "acknowledgment_required": True,
                "message": (
                    f"Spending cap set to ${cap_decimal}. "
                    "WARNING: AI stops accepting tickets when limit reached."
                ),
            }

    # ── Public API: SC1 ──────────────────────────────────────────────────

    def get_spending_cap(
        self,
        company_id: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current spending cap settings for a company. (SC1)

        Args:
            company_id: Company UUID or str

        Returns:
            Dict with cap settings, or None if no cap set:
                - company_id, max_overage_amount, alert_thresholds,
                  is_active, current_overage
        """
        company_id_str = self._validate_company_id(company_id)

        with SessionLocal() as db:
            SpendingCap = self._get_or_create_cap_table(db)
            if SpendingCap is None:
                return None

            cap = (
                db.query(SpendingCap)
                .filter(
                    SpendingCap.company_id == company_id_str,
                    SpendingCap.is_active is True,  # noqa: E712
                )
                .first()
            )

            if cap is None:
                return None

            # Parse thresholds
            try:
                thresholds = json.loads(cap.alert_thresholds)
            except (json.JSONDecodeError, TypeError):
                thresholds = DEFAULT_THRESHOLDS

            current_overage = self._get_current_month_overage(
                db, company_id_str)

            return {
                "company_id": cap.company_id,
                "max_overage_amount": str(cap.max_overage_amount),
                "alert_thresholds": thresholds,
                "is_active": bool(cap.is_active),
                "current_overage": str(current_overage),
                "remaining": str(
                    self._round_money(cap.max_overage_amount - current_overage)
                ),
                "usage_percent": (
                    float(
                        self._round_money(
                            current_overage / cap.max_overage_amount * 100
                        )
                    )
                    if cap.max_overage_amount > 0
                    else 0.0
                ),
            }

    # ── Public API: SC4 ──────────────────────────────────────────────────

    def remove_spending_cap(
        self,
        company_id: Any,
    ) -> Dict[str, Any]:
        """
        Remove the spending cap for a company (no-cap mode). (SC4)

        Args:
            company_id: Company UUID or str

        Returns:
            Dict with removal confirmation
        """
        company_id_str = self._validate_company_id(company_id)

        with SessionLocal() as db:
            SpendingCap = self._get_or_create_cap_table(db)
            if SpendingCap is None:
                return {
                    "company_id": company_id_str,
                    "removed": False,
                    "message": "No spending cap table available",
                }

            deleted = (
                db.query(SpendingCap)
                .filter(SpendingCap.company_id == company_id_str)
                .delete()
            )
            db.commit()

            if deleted:
                logger.info(
                    "spending_cap_removed company_id=%s",
                    company_id_str,
                )
            else:
                logger.info(
                    "spending_cap_remove_noop company_id=%s",
                    company_id_str,
                )

            return {
                "company_id": company_id_str,
                "removed": deleted > 0,
                "message": (
                    "Spending cap removed. Overage is now unlimited."
                    if deleted
                    else "No spending cap was set."
                ),
            }

    # ── Public API: SC2 ──────────────────────────────────────────────────

    def check_cap_before_overage(
        self,
        company_id: Any,
        proposed_charge: Any,
    ) -> Dict[str, Any]:
        """
        Check if a proposed overage charge would exceed the spending cap. (SC2)

        Calculates current overage for the period and determines if
        adding the proposed_charge would breach the cap.

        Args:
            company_id: Company UUID or str
            proposed_charge: Proposed charge amount (Decimal/str/float)

        Returns:
            Dict with:
                - allowed (bool): Whether the charge is within cap
                - remaining (Decimal): Remaining cap after charge
                - would_exceed (bool): Whether this charge alone would
                  push over the cap
                - message (str): Human-readable status message
                - current_overage (Decimal): Current period overage total
                - max_overage_amount (Decimal or None): The cap, if set
        """
        company_id_str = self._validate_company_id(company_id)

        # BC-002: Convert to Decimal
        try:
            charge_decimal = Decimal(str(proposed_charge))
        except Exception:
            raise SpendingCapError(
                f"Invalid proposed_charge: {proposed_charge}"
            )

        if charge_decimal < Decimal("0"):
            raise SpendingCapError("proposed_charge must be non-negative")

        with SessionLocal() as db:
            # Get the cap
            SpendingCap = self._get_or_create_cap_table(db)
            if SpendingCap is None:
                # No table = no cap = allow everything
                logger.info(
                    "cap_check_table_unavailable company_id=%s charge=%s allowed=true",
                    company_id_str,
                    charge_decimal,
                )
                return {
                    "allowed": True,
                    "remaining": None,
                    "would_exceed": False,
                    "current_overage": "0.00",
                    "max_overage_amount": None,
                    "message": "No spending cap configured.",
                }

            cap = (
                db.query(SpendingCap)
                .filter(
                    SpendingCap.company_id == company_id_str,
                    SpendingCap.is_active is True,  # noqa: E712
                )
                .first()
            )

            if cap is None:
                # No cap set (SC4) = unlimited
                return {
                    "allowed": True,
                    "remaining": None,
                    "would_exceed": False,
                    "current_overage": "0.00",
                    "max_overage_amount": None,
                    "message": "No spending cap configured. Overage is unlimited.",
                }

            max_cap: Decimal = cap.max_overage_amount
            current_overage = self._get_current_month_overage(
                db, company_id_str)

            # Calculate what would happen with this charge
            new_total = current_overage + charge_decimal
            remaining = max_cap - current_overage

            if current_overage >= max_cap:
                # Already at or over cap
                logger.warning(
                    "spending_cap_already_exceeded "
                    "company_id=%s current=%s cap=%s",
                    company_id_str,
                    current_overage,
                    max_cap,
                )
                return {
                    "allowed": False,
                    "remaining": Decimal("0.00"),
                    "would_exceed": True,
                    "current_overage": str(current_overage),
                    "max_overage_amount": str(max_cap),
                    "message": (
                        f"You've reached your ${max_cap} overage cap. "
                        "New tickets are blocked."
                    ),
                }

            if new_total > max_cap:
                # This charge would push over the cap
                logger.warning(
                    "spending_cap_would_exceed "
                    "company_id=%s current=%s proposed=%s cap=%s",
                    company_id_str,
                    current_overage,
                    charge_decimal,
                    max_cap,
                )
                return {
                    "allowed": False,
                    "remaining": str(self._round_money(remaining)),
                    "would_exceed": True,
                    "current_overage": str(current_overage),
                    "max_overage_amount": str(max_cap),
                    "message": (
                        f"This charge would exceed your ${max_cap} overage cap. "
                        f"Remaining: ${self._round_money(remaining)}."
                    ),
                }

            # Within cap
            logger.info(
                "spending_cap_check_passed "
                "company_id=%s current=%s proposed=%s cap=%s remaining=%s",
                company_id_str,
                current_overage,
                charge_decimal,
                max_cap,
                self._round_money(remaining - charge_decimal),
            )
            return {
                "allowed": True,
                "remaining": str(
                    self._round_money(remaining - charge_decimal)
                ),
                "would_exceed": False,
                "current_overage": str(current_overage),
                "max_overage_amount": str(max_cap),
                "message": "Within spending cap.",
            }

    # ── Public API: SC3 ──────────────────────────────────────────────────

    def check_soft_cap_alerts(
        self,
        company_id: Any,
        current_overage_amount: Any,
    ) -> Dict[str, Any]:
        """
        Check which soft-cap alert thresholds should fire. (SC3)

        Evaluates each configured threshold (50%, 75%, 90%) against
        the current overage. Only returns thresholds that have been
        crossed for the first time (tracked via sent alerts to prevent
        duplicate notifications within the same billing period).

        Args:
            company_id: Company UUID or str
            current_overage_amount: Current overage amount (Decimal/str/float)

        Returns:
            Dict with:
                - alerts (List[Dict]): Thresholds that should trigger alerts
                - already_sent (List[int]): Thresholds already notified
                - current_percent (float): Current usage percentage
        """
        company_id_str = self._validate_company_id(company_id)

        # BC-002: Convert to Decimal
        try:
            overage_decimal = Decimal(str(current_overage_amount))
        except Exception:
            raise SpendingCapError(
                f"Invalid current_overage_amount: {current_overage_amount}"
            )

        with SessionLocal() as db:
            SpendingCap = self._get_or_create_cap_table(db)
            if SpendingCap is None:
                return {
                    "alerts": [],
                    "already_sent": [],
                    "current_percent": 0.0,
                    "message": "No spending cap configured.",
                }

            cap = (
                db.query(SpendingCap)
                .filter(
                    SpendingCap.company_id == company_id_str,
                    SpendingCap.is_active is True,  # noqa: E712
                )
                .first()
            )

            if cap is None:
                return {
                    "alerts": [],
                    "already_sent": [],
                    "current_percent": 0.0,
                    "message": "No spending cap configured.",
                }

            max_cap = cap.max_overage_amount
            if max_cap <= 0:
                return {
                    "alerts": [],
                    "already_sent": [],
                    "current_percent": 0.0,
                    "message": "Invalid cap amount.",
                }

            # Calculate current percentage
            current_percent = float(
                self._round_money(overage_decimal / max_cap * 100)
            )

            # Parse thresholds and already-sent list
            try:
                thresholds = json.loads(cap.alert_thresholds)
            except (json.JSONDecodeError, TypeError):
                thresholds = DEFAULT_THRESHOLDS

            # Parse already-sent alerts from the record
            try:
                soft_cap_sent_field = getattr(
                    cap, "soft_cap_alerts_sent", None)
                if soft_cap_sent_field:
                    already_sent = json.loads(soft_cap_sent_field)
                else:
                    already_sent = []
            except (json.JSONDecodeError, TypeError):
                already_sent = []

            # Determine which thresholds fire
            alerts: List[Dict[str, Any]] = []
            newly_sent: List[int] = []

            for threshold in thresholds:
                if threshold in already_sent:
                    continue  # Already notified for this threshold
                if current_percent >= float(threshold):
                    alerts.append({
                        "threshold": threshold,
                        "current_percent": current_percent,
                        "current_overage": str(overage_decimal),
                        "max_cap": str(max_cap),
                        "message": (
                            f"Overage has reached {threshold}% of your "
                            f"${max_cap} spending cap "
                            f"(${overage_decimal} / ${max_cap})."
                        ),
                    })
                    newly_sent.append(threshold)

            # Update sent list
            if newly_sent:
                updated_sent = sorted(set(already_sent + newly_sent))
                if hasattr(cap, "soft_cap_alerts_sent"):
                    cap.soft_cap_alerts_sent = json.dumps(updated_sent)
                    cap.updated_at = datetime.now(timezone.utc)
                    db.commit()

                logger.info(
                    "soft_cap_alerts_fired "
                    "company_id=%s thresholds=%s current_percent=%.1f%%",
                    company_id_str,
                    newly_sent,
                    current_percent,
                )

            return {
                "alerts": alerts,
                "already_sent": already_sent,
                "current_percent": current_percent,
                "message": f"{len(alerts)} alert(s) triggered.",
            }

    # ── Public API: SC2 ──────────────────────────────────────────────────

    def enforce_hard_cap(
        self,
        company_id: Any,
        current_overage_amount: Any,
    ) -> Dict[str, Any]:
        """
        Enforce the hard spending cap. (SC2)

        If current overage >= max cap, returns action="block_tickets".
        Otherwise returns action="allow".

        This is the final enforcement point before ticket processing.

        Args:
            company_id: Company UUID or str
            current_overage_amount: Current overage amount (Decimal/str/float)

        Returns:
            Dict with:
                - action (str): "block_tickets" or "allow"
                - current_overage (str): Current overage amount
                - max_cap (str or None): The configured cap
                - message (str): Action description
        """
        company_id_str = self._validate_company_id(company_id)

        # BC-002: Convert to Decimal
        try:
            overage_decimal = Decimal(str(current_overage_amount))
        except Exception:
            raise SpendingCapError(
                f"Invalid current_overage_amount: {current_overage_amount}"
            )

        with SessionLocal() as db:
            SpendingCap = self._get_or_create_cap_table(db)
            if SpendingCap is None:
                return {
                    "action": "allow",
                    "current_overage": str(overage_decimal),
                    "max_cap": None,
                    "message": "No cap configured — allowing.",
                }

            cap = (
                db.query(SpendingCap)
                .filter(
                    SpendingCap.company_id == company_id_str,
                    SpendingCap.is_active is True,  # noqa: E712
                )
                .first()
            )

            if cap is None:
                return {
                    "action": "allow",
                    "current_overage": str(overage_decimal),
                    "max_cap": None,
                    "message": "No spending cap configured — allowing.",
                }

            max_cap = cap.max_overage_amount

            if overage_decimal >= max_cap:
                logger.warning(
                    "hard_cap_enforced_block "
                    "company_id=%s current=%s cap=%s",
                    company_id_str,
                    overage_decimal,
                    max_cap,
                )
                return {
                    "action": "block_tickets",
                    "current_overage": str(overage_decimal),
                    "max_cap": str(max_cap),
                    "message": (
                        f"Hard cap reached: ${overage_decimal} >= ${max_cap}. "
                        "Tickets are blocked until next billing period."
                    ),
                }

            return {
                "action": "allow",
                "current_overage": str(overage_decimal),
                "max_cap": str(max_cap),
                "message": "Within hard cap — allowing.",
            }


# ── Singleton Service ────────────────────────────────────────────────────

_spending_cap_service: Optional[SpendingCapService] = None


def get_spending_cap_service() -> SpendingCapService:
    """
    Get the spending cap service singleton.

    Returns:
        Shared SpendingCapService instance
    """
    global _spending_cap_service
    if _spending_cap_service is None:
        _spending_cap_service = SpendingCapService()
    return _spending_cap_service
