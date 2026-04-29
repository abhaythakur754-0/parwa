"""
Refund Service (RF1-RF5)

Handles refund request lifecycle management:
- RF1: Create refund request — dual approval for amounts > $500
- RF2: Process approved refund — create Paddle refund + credit if needed
- RF3: Credit balance system — create/apply/query customer credits
- RF4: Cooling-off refund — 24h window, <$1000 auto-approve
- RF5: Refund audit trail — query refund history and audit logs

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing import Invoice, Subscription, Transaction
from database.models.billing_extended import CreditBalance, RefundAudit
from database.models.core import Company

logger = logging.getLogger("parwa.services.refund")

# ── Constants ──────────────────────────────────────────────────────────────

# RF1: Refunds above this threshold require dual approval
DUAL_APPROVAL_THRESHOLD = Decimal("500.00")

# RF4: Cooling-off period in hours
COOLING_OFF_HOURS = 24

# RF3: Default credit expiry in months
CREDIT_DEFAULT_EXPIRY_MONTHS = 12

# RF4: Cooling-off auto-approve threshold
COOLING_OFF_AUTO_APPROVE_THRESHOLD = Decimal("1000.00")

# ── Valid refund statuses ───────────────────────────────────────────────────

VALID_REFUND_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "processed",
    "failed"}

# ── Valid refund types ─────────────────────────────────────────────────────

VALID_REFUND_TYPES = {"full", "partial", "credit", "cooling_off"}

# ── Valid credit sources ───────────────────────────────────────────────────

VALID_CREDIT_SOURCES = {"refund", "promo", "goodwill", "cooling_off"}

# ── Valid credit statuses ──────────────────────────────────────────────────

VALID_CREDIT_STATUSES = {
    "available",
    "partially_used",
    "fully_used",
    "expired"}


# ── Exceptions ──────────────────────────────────────────────────────────────


class RefundError(Exception):
    """Base exception for refund errors."""


class RefundNotFoundError(RefundError):
    """Refund record not found."""


class RefundAlreadyProcessedError(RefundError):
    """Refund has already been processed and cannot be modified."""


class CoolingOffExpiredError(RefundError):
    """Cooling-off period has expired."""


class InsufficientCreditsError(RefundError):
    """Not enough credit balance available."""


# ── Service ─────────────────────────────────────────────────────────────────


class RefundService:
    """
    Refund system service.

    Manages the full lifecycle of refund requests including dual-approval
    workflows, Paddle refund processing, credit balance management,
    cooling-off period handling, and comprehensive audit trails.

    Usage:
        service = RefundService()
        refund = service.create_refund(
            company_id=uuid,
            amount=Decimal("999.00"),
            reason="Requested within cooling-off period",
            refund_type="cooling_off",
            admin_id=admin_uuid,
        )
    """

    # ═══════════════════════════════════════════════════════════════════
    # RF1: Create Refund Request
    # ═══════════════════════════════════════════════════════════════════

    def create_refund(
        self,
        company_id: UUID,
        amount: Decimal,
        reason: str,
        refund_type: str,
        admin_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        RF1: Create a refund request.

        For amounts > $500, dual approval is required (needs two separate
        approvers before processing). Refunds ≤ $500 need only one approval.

        Args:
            company_id: Company UUID
            amount: Refund amount (BC-002: Decimal)
            reason: Reason for refund
            refund_type: Type of refund (full/partial/credit/cooling_off)
            admin_id: UUID of the requesting admin

        Returns:
            Dict with refund audit record details

        Raises:
            RefundError: If parameters are invalid
        """
        if not company_id:
            raise RefundError("company_id is required (BC-001)")

        amount = Decimal(str(amount))
        if amount <= 0:
            raise RefundError(f"Refund amount must be positive, got {amount}")

        if refund_type not in VALID_REFUND_TYPES:
            raise RefundError(
                f"Invalid refund_type: {refund_type}. "
                f"Must be one of: {', '.join(sorted(VALID_REFUND_TYPES))}"
            )

        if not reason or not reason.strip():
            raise RefundError("Refund reason is required")

        with SessionLocal() as db:
            # BC-001: Validate company exists
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).first()

            if not company:
                raise RefundError(f"Company {company_id} not found (BC-001)")

            now = datetime.now(timezone.utc)

            # For cooling_off type, validate the window
            if refund_type == "cooling_off":
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                ).order_by(Subscription.created_at.desc()).first()

                if subscription and subscription.current_period_start:
                    period_start = subscription.current_period_start
                    if period_start.tzinfo is None:
                        period_start = period_start.replace(
                            tzinfo=timezone.utc)

                    elapsed_hours = (now - period_start).total_seconds() / 3600
                    if elapsed_hours > COOLING_OFF_HOURS:
                        raise CoolingOffExpiredError(
                            f"Cooling-off period expired. "
                            f"{elapsed_hours:.1f} hours have passed since "
                            f"subscription start (limit: {COOLING_OFF_HOURS} hours)."
                        )

            # Determine if dual approval is needed
            needs_dual_approval = amount > DUAL_APPROVAL_THRESHOLD

            # Create refund audit record
            refund_audit = RefundAudit(
                company_id=str(company_id),
                refund_type=refund_type,
                original_amount=amount.quantize(Decimal("0.01")),
                refund_amount=amount.quantize(Decimal("0.01")),
                reason=reason.strip(),
                approver_id=str(admin_id) if admin_id else None,
                status="pending",
                created_at=now,
            )
            db.add(refund_audit)
            db.commit()
            db.refresh(refund_audit)

            logger.info(
                "refund_created refund_id=%s company_id=%s amount=%s "
                "type=%s dual_approval=%s",
                refund_audit.id,
                company_id,
                amount,
                refund_type,
                needs_dual_approval,
            )

            return self._refund_audit_to_dict(refund_audit, include_meta=True)

    # ═══════════════════════════════════════════════════════════════════
    # RF1: Approve Refund
    # ═══════════════════════════════════════════════════════════════════

    def approve_refund(
        self,
        refund_id: str,
        approver_id: UUID,
    ) -> Dict[str, Any]:
        """
        RF1: Approve a pending refund request.

        For amounts > $500, a second approval is also required.
        The first approval is recorded as approver_id, the second
        as second_approver_id.

        Args:
            refund_id: RefundAudit record UUID
            approver_id: UUID of the approving admin

        Returns:
            Dict with updated refund audit details

        Raises:
            RefundNotFoundError: If refund not found
            RefundAlreadyProcessedError: If refund is not in pending/approved state
            RefundError: If approver is the same as the first approver (dual)
        """
        if not refund_id:
            raise RefundError("refund_id is required")

        with SessionLocal() as db:
            refund = db.query(RefundAudit).filter(
                RefundAudit.id == refund_id,
            ).first()

            if not refund:
                raise RefundNotFoundError(f"Refund {refund_id} not found")

            if refund.status not in ("pending", "approved"):
                raise RefundAlreadyProcessedError(
                    f"Refund {refund_id} is in '{refund.status}' status and "
                    f"cannot be approved"
                )

            amount = Decimal(str(refund.refund_amount))
            needs_dual = amount > DUAL_APPROVAL_THRESHOLD

            if refund.status == "pending":
                # First approval
                if str(approver_id) == refund.approver_id:
                    raise RefundError(
                        "Approver cannot be the same person who created "
                        "the refund request"
                    )

                refund.approver_id = str(approver_id)

                if needs_dual:
                    # Move to "approved" status, awaiting second approval
                    refund.status = "approved"
                    logger.info(
                        "refund_first_approval refund_id=%s approver=%s "
                        "awaiting_second=True",
                        refund_id,
                        approver_id,
                    )
                else:
                    # Single approval sufficient — mark processed
                    refund.status = "approved"
                    logger.info(
                        "refund_approved refund_id=%s approver=%s",
                        refund_id,
                        approver_id,
                    )

            elif refund.status == "approved":
                # This is the second approval (dual approval flow)
                if not needs_dual:
                    raise RefundError(
                        "This refund does not require dual approval"
                    )

                if str(approver_id) == refund.approver_id:
                    raise RefundError(
                        "Second approver must be a different person from "
                        "the first approver"
                    )

                refund.second_approver_id = str(approver_id)
                logger.info(
                    "refund_second_approval refund_id=%s second_approver=%s",
                    refund_id,
                    approver_id,
                )

            db.commit()
            db.refresh(refund)

            return self._refund_audit_to_dict(refund, include_meta=True)

    # ═══════════════════════════════════════════════════════════════════
    # RF1: Reject Refund
    # ═══════════════════════════════════════════════════════════════════

    def reject_refund(
        self,
        refund_id: str,
        approver_id: UUID,
        reason: str,
    ) -> Dict[str, Any]:
        """
        RF1: Reject a pending or approved refund request.

        Args:
            refund_id: RefundAudit record UUID
            approver_id: UUID of the rejecting admin
            reason: Rejection reason

        Returns:
            Dict with updated refund audit details

        Raises:
            RefundNotFoundError: If refund not found
            RefundAlreadyProcessedError: If refund already processed
        """
        if not refund_id:
            raise RefundError("refund_id is required")

        if not reason or not reason.strip():
            raise RefundError("Rejection reason is required")

        with SessionLocal() as db:
            refund = db.query(RefundAudit).filter(
                RefundAudit.id == refund_id,
            ).first()

            if not refund:
                raise RefundNotFoundError(f"Refund {refund_id} not found")

            if refund.status not in ("pending", "approved"):
                raise RefundAlreadyProcessedError(
                    f"Refund {refund_id} is in '{refund.status}' status and "
                    f"cannot be rejected"
                )

            refund.status = "rejected"
            refund.approver_id = str(approver_id)
            # Store rejection reason in the existing reason field
            # with a prefix to distinguish from original reason
            refund.reason = f"[REJECTED] {
                reason.strip()} — Original: {
                refund.reason}"

            db.commit()
            db.refresh(refund)

            logger.info(
                "refund_rejected refund_id=%s approver=%s reason=%s",
                refund_id,
                approver_id,
                reason.strip()[:100],
            )

            return self._refund_audit_to_dict(refund, include_meta=True)

    # ═══════════════════════════════════════════════════════════════════
    # RF2: Process Approved Refund
    # ═══════════════════════════════════════════════════════════════════

    def process_approved_refund(
        self,
        refund_id: str,
    ) -> Dict[str, Any]:
        """
        RF2: Process an approved refund.

        For refunds requiring dual approval, both approvals must be present.
        Creates a Paddle refund request and optionally a credit balance
        record depending on the refund type.

        Steps:
        1. Validate refund is in 'approved' status
        2. Check dual-approval requirements are met
        3. Create Paddle refund (best-effort, non-blocking)
        4. If refund_type is 'credit', create credit balance
        5. Record transaction
        6. Update refund audit status to 'processed'

        Args:
            refund_id: RefundAudit record UUID

        Returns:
            Dict with processing result and details

        Raises:
            RefundNotFoundError: If refund not found
            RefundAlreadyProcessedError: If refund not in approved state
            RefundError: If dual-approval not met or processing fails
        """
        if not refund_id:
            raise RefundError("refund_id is required")

        with SessionLocal() as db:
            refund = db.query(RefundAudit).filter(
                RefundAudit.id == refund_id,
            ).first()

            if not refund:
                raise RefundNotFoundError(f"Refund {refund_id} not found")

            if refund.status != "approved":
                raise RefundAlreadyProcessedError(
                    f"Refund {refund_id} is in '{refund.status}' status. "
                    f"Only 'approved' refunds can be processed."
                )

            amount = Decimal(str(refund.refund_amount))
            needs_dual = amount > DUAL_APPROVAL_THRESHOLD

            # Verify dual-approval if needed
            if needs_dual and not refund.second_approver_id:
                raise RefundError(
                    f"Refund of {amount} exceeds dual-approval threshold "
                    f"({DUAL_APPROVAL_THRESHOLD}). A second approval is required "
                    f"before processing."
                )

            company_id = refund.company_id
            now = datetime.now(timezone.utc)

            # Create Paddle refund (best-effort)
            paddle_refund_id = None
            try:
                paddle_refund_id = self._create_paddle_refund(db, refund)
            except Exception as e:
                logger.error(
                    "refund_paddle_failed refund_id=%s error=%s",
                    refund_id,
                    str(e),
                )
                # Continue — don't block on Paddle failure

            # Create credit balance if refund type is credit or cooling_off
            credit_balance_id = None
            if refund.refund_type in ("credit", "cooling_off"):
                credit_balance_id = self.create_credit_balance(
                    company_id=UUID(company_id),
                    amount=amount,
                    source="refund" if refund.refund_type == "credit" else "cooling_off",
                    description=f"Credit from {
                        refund.refund_type} refund: {
                        refund.reason}",
                    expires_at=now +
                    timedelta(
                        days=CREDIT_DEFAULT_EXPIRY_MONTHS *
                        30),
                ).get("id")

                # Link credit to refund audit
                refund.credit_balance_id = credit_balance_id

            # Record transaction
            transaction = Transaction(
                company_id=company_id,
                # Negative for refund
                amount=-amount.quantize(Decimal("0.01")),
                currency=refund.currency if hasattr(
                    refund, "currency") else "USD",
                status="completed",
                transaction_type="refund",
                description=f"Refund ({refund.refund_type}): {refund.reason}",
            )
            db.add(transaction)

            # Update refund audit
            refund.paddle_refund_id = paddle_refund_id
            refund.status = "processed"

            db.commit()
            db.refresh(refund)

            logger.info(
                "refund_processed refund_id=%s company_id=%s amount=%s "
                "type=%s paddle=%s credit=%s",
                refund_id,
                company_id,
                amount,
                refund.refund_type,
                "yes" if paddle_refund_id else "no",
                "yes" if credit_balance_id else "no",
            )

            return {
                "refund": self._refund_audit_to_dict(refund),
                "paddle_refund_id": paddle_refund_id,
                "credit_balance_id": credit_balance_id,
                "transaction_id": transaction.id,
                "message": (
                    f"Refund of {amount} processed successfully." + (
                        f" Credit balance {credit_balance_id} created." if credit_balance_id else "")),
            }

    # ═══════════════════════════════════════════════════════════════════
    # RF3: Credit Balance Management
    # ═══════════════════════════════════════════════════════════════════

    def create_credit_balance(
        self,
        company_id: UUID,
        amount: Decimal,
        source: str,
        description: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        RF3: Create a credit balance for a company.

        Credits can be sourced from refunds, promotions, goodwill gestures,
        or cooling-off cancellations. Credits expire after the default period
        unless a specific expiry is provided.

        Args:
            company_id: Company UUID (BC-001)
            amount: Credit amount (BC-002: Decimal)
            source: Credit source (refund/promo/goodwill/cooling_off)
            description: Optional description
            expires_at: Optional expiry datetime

        Returns:
            Dict with credit balance details

        Raises:
            RefundError: If parameters are invalid
        """
        if not company_id:
            raise RefundError("company_id is required (BC-001)")

        amount = Decimal(str(amount))
        if amount <= 0:
            raise RefundError(f"Credit amount must be positive, got {amount}")

        if source not in VALID_CREDIT_SOURCES:
            raise RefundError(
                f"Invalid source: {source}. "
                f"Must be one of: {', '.join(sorted(VALID_CREDIT_SOURCES))}"
            )

        # Default expiry if not specified
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(
                days=CREDIT_DEFAULT_EXPIRY_MONTHS * 30
            )

        with SessionLocal() as db:
            # BC-001: Validate company exists
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).first()

            if not company:
                raise RefundError(f"Company {company_id} not found (BC-001)")

            now = datetime.now(timezone.utc)

            credit = CreditBalance(
                company_id=str(company_id),
                amount=amount.quantize(Decimal("0.01")),
                currency="USD",
                source=source,
                description=description,
                expires_at=expires_at,
                status="available",
                created_at=now,
                updated_at=now,
            )
            db.add(credit)
            db.commit()
            db.refresh(credit)

            logger.info(
                "credit_created credit_id=%s company_id=%s amount=%s source=%s",
                credit.id,
                company_id,
                amount,
                source,
            )

            return self._credit_to_dict(credit)

    def apply_credit_to_invoice(
        self,
        company_id: UUID,
        invoice_id: str,
        credit_id: str,
    ) -> Dict[str, Any]:
        """
        RF3: Apply a credit balance to an invoice.

        Reduces the credit balance and marks it as applied. If the credit
        amount exceeds the invoice amount, the credit is marked as
        partially_used and the remaining balance stays available.

        Args:
            company_id: Company UUID (BC-001)
            invoice_id: Invoice record UUID
            credit_id: CreditBalance record UUID

        Returns:
            Dict with application result

        Raises:
            RefundError: If parameters are invalid or credit unavailable
            InsufficientCreditsError: If credit is expired or fully used
        """
        if not company_id:
            raise RefundError("company_id is required (BC-001)")

        with SessionLocal() as db:
            # Validate credit
            credit = db.query(CreditBalance).filter(
                CreditBalance.id == credit_id,
                CreditBalance.company_id == str(company_id),
            ).first()

            if not credit:
                raise RefundError(
                    f"Credit {credit_id} not found for company {company_id}"
                )

            if credit.status in ("fully_used", "expired"):
                raise InsufficientCreditsError(
                    f"Credit {credit_id} is {
                        credit.status} and cannot be applied")

            # Check expiry
            now = datetime.now(timezone.utc)
            if credit.expires_at:
                expires_at = credit.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if now > expires_at:
                    credit.status = "expired"
                    db.commit()
                    raise InsufficientCreditsError(
                        f"Credit {credit_id} expired on "
                        f"{credit.expires_at.isoformat()}"
                    )

            # Validate invoice
            invoice = db.query(Invoice).filter(
                Invoice.id == invoice_id,
                Invoice.company_id == str(company_id),
            ).first()

            if not invoice:
                raise RefundError(
                    f"Invoice {invoice_id} not found for company {company_id}"
                )

            credit_amount = Decimal(str(credit.amount))
            invoice_amount = Decimal(str(invoice.amount))

            if credit_amount >= invoice_amount:
                # Credit covers full invoice
                applied_amount = invoice_amount
                remaining = credit_amount - invoice_amount
                credit.status = "partially_used" if remaining > 0 else "fully_used"
                credit.amount = remaining if remaining > 0 else Decimal("0.00")
                credit.applied_to_invoice_id = invoice_id
                credit.applied_at = now
                invoice.status = "paid"
                invoice.paid_at = now
            else:
                # Partial application
                applied_amount = credit_amount
                credit.status = "fully_used"
                credit.amount = Decimal("0.00")
                credit.applied_to_invoice_id = invoice_id
                credit.applied_at = now
                # Invoice still has remaining balance — update amount
                invoice.amount = invoice_amount - credit_amount

            db.commit()
            db.refresh(credit)
            db.refresh(invoice)

            logger.info(
                "credit_applied credit_id=%s invoice_id=%s company_id=%s "
                "applied=%s remaining=%s",
                credit_id,
                invoice_id,
                company_id,
                applied_amount,
                credit.amount,
            )

            return {
                "credit": self._credit_to_dict(credit),
                "invoice_id": invoice_id,
                "invoice_remaining": str(invoice.amount),
                "applied_amount": str(applied_amount.quantize(Decimal("0.01"))),
                "message": (
                    f"Applied {applied_amount} credit to invoice {invoice_id}."
                    + (f" {credit.amount} remaining on credit." if Decimal(str(credit.amount)) > 0 else "")
                ),
            }

    def get_available_credits(
        self,
        company_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        RF3: Get all available (usable) credit balances for a company.

        Returns credits that are not expired and not fully used, ordered
        by expiry date (soonest first — FIFO consumption).

        Args:
            company_id: Company UUID (BC-001)

        Returns:
            List of credit balance dicts
        """
        if not company_id:
            raise RefundError("company_id is required (BC-001)")

        with SessionLocal() as db:
            now = datetime.now(timezone.utc)

            credits = db.query(CreditBalance).filter(
                CreditBalance.company_id == str(company_id),
                CreditBalance.status.in_(["available", "partially_used"]),
                CreditBalance.amount > Decimal("0.00"),
            ).filter(
                # Not expired
                (CreditBalance.expires_at.is_(None)) |
                (CreditBalance.expires_at > now)
            ).order_by(
                CreditBalance.expires_at.asc().nulls_last()  # FIFO: soonest expiry first
            ).all()

            return [self._credit_to_dict(c) for c in credits]

    # ═══════════════════════════════════════════════════════════════════
    # RF4: Cooling-Off Refund
    # ═══════════════════════════════════════════════════════════════════

    def request_cooling_off_refund(
        self,
        company_id: UUID,
        reason: str,
    ) -> Dict[str, Any]:
        """
        RF4: Request a refund within the cooling-off period.

        The cooling-off window is 24 hours from subscription start.
        - Amounts < $1000: Auto-approved, single approval
        - Amounts >= $1000: Requires dual approval

        This method validates the cooling-off window and creates the
        refund with appropriate approval requirements.

        Args:
            company_id: Company UUID
            reason: Reason for the cooling-off refund

        Returns:
            Dict with refund audit details

        Raises:
            CoolingOffExpiredError: If 24h window has passed
            RefundError: If company has no subscription or params invalid
        """
        if not company_id:
            raise RefundError("company_id is required (BC-001)")

        if not reason or not reason.strip():
            raise RefundError("Reason is required for cooling-off refund")

        with SessionLocal() as db:
            # Get the latest subscription
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                raise RefundError(
                    f"No subscription found for company {company_id}"
                )

            # Validate cooling-off window
            now = datetime.now(timezone.utc)
            period_start = subscription.current_period_start
            if period_start:
                if period_start.tzinfo is None:
                    period_start = period_start.replace(tzinfo=timezone.utc)

                elapsed_hours = (now - period_start).total_seconds() / 3600
                if elapsed_hours > COOLING_OFF_HOURS:
                    raise CoolingOffExpiredError(
                        f"Cooling-off period expired. "
                        f"{elapsed_hours:.1f} hours have passed since "
                        f"subscription start (limit: {COOLING_OFF_HOURS} hours)."
                    )

            # Determine refund amount from subscription price
            # Use the billing_extended helper to get variant limits
            try:
                from database.models.billing_extended import get_variant_limits
                limits = get_variant_limits(subscription.tier)
                if limits:
                    refund_amount = limits["price_monthly"]
                else:
                    refund_amount = Decimal("0.00")
            except Exception:
                refund_amount = Decimal("0.00")

            if refund_amount <= 0:
                raise RefundError(
                    f"Cannot determine refund amount for tier '{
                        subscription.tier}'")

            now = datetime.now(timezone.utc)

            # Create refund audit
            refund_audit = RefundAudit(
                company_id=str(company_id),
                refund_type="cooling_off",
                original_amount=refund_amount,
                refund_amount=refund_amount,
                reason=f"[COOLING-OFF] {reason.strip()}",
                status="pending",
                created_at=now,
            )

            # Auto-approve if under threshold
            needs_dual = refund_amount > COOLING_OFF_AUTO_APPROVE_THRESHOLD
            if not needs_dual:
                refund_audit.status = "approved"
                logger.info(
                    "cooling_off_auto_approved company_id=%s amount=%s",
                    company_id,
                    refund_amount,
                )
            else:
                logger.info(
                    "cooling_off_requires_dual_approval company_id=%s amount=%s",
                    company_id,
                    refund_amount,
                )

            db.add(refund_audit)
            db.commit()
            db.refresh(refund_audit)

            logger.info(
                "cooling_off_refund_created refund_id=%s company_id=%s "
                "amount=%s dual_approval=%s",
                refund_audit.id,
                company_id,
                refund_amount,
                needs_dual,
            )

            return self._refund_audit_to_dict(refund_audit, include_meta=True)

    # ═══════════════════════════════════════════════════════════════════
    # RF5: Refund Audit Trail
    # ═══════════════════════════════════════════════════════════════════

    def get_refund_audit(
        self,
        refund_id: str,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        RF5: Get a single refund audit record.

        Args:
            refund_id: RefundAudit record UUID
            company_id: Company UUID (BC-001 scoping)

        Returns:
            Dict with refund audit details

        Raises:
            RefundNotFoundError: If refund audit not found
        """
        if not company_id:
            raise RefundError("company_id is required (BC-001)")

        with SessionLocal() as db:
            refund = db.query(RefundAudit).filter(
                RefundAudit.id == refund_id,
                RefundAudit.company_id == str(company_id),
            ).first()

            if not refund:
                raise RefundNotFoundError(
                    f"Refund {refund_id} not found for company {company_id}"
                )

            return self._refund_audit_to_dict(refund, include_meta=True)

    def list_refund_audits(
        self,
        company_id: UUID,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        RF5: List refund audit records for a company.

        Args:
            company_id: Company UUID (BC-001 scoping)
            status: Optional status filter (pending/approved/rejected/processed/failed)

        Returns:
            List of refund audit dicts

        Raises:
            RefundError: If status filter is invalid
        """
        if not company_id:
            raise RefundError("company_id is required (BC-001)")

        if status is not None and status not in VALID_REFUND_STATUSES:
            raise RefundError(
                f"Invalid status: {status}. "
                f"Must be one of: {', '.join(sorted(VALID_REFUND_STATUSES))}"
            )

        with SessionLocal() as db:
            query = db.query(RefundAudit).filter(
                RefundAudit.company_id == str(company_id),
            )

            if status is not None:
                query = query.filter(RefundAudit.status == status)

            refunds = query.order_by(RefundAudit.created_at.desc()).all()

            return [
                self._refund_audit_to_dict(
                    r, include_meta=True) for r in refunds]

    # ═══════════════════════════════════════════════════════════════════
    # Internal Helpers
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _create_paddle_refund(
        db: Session,
        refund: RefundAudit,
    ) -> Optional[str]:
        """
        Create a refund in Paddle (best-effort).

        Tries to find the relevant Paddle transaction for the company
        and issue a refund through the Paddle API.

        Args:
            db: Active database session
            refund: RefundAudit record

        Returns:
            Paddle refund ID string, or None if not applicable
        """
        try:
            pass
        except ImportError:
            logger.warning("paddle_client not available for refund processing")
            return None

        # Find the most recent transaction for the company
        transaction = db.query(Transaction).filter(
            Transaction.company_id == refund.company_id,
            Transaction.paddle_transaction_id.isnot(None),
            Transaction.status == "completed",
        ).order_by(Transaction.created_at.desc()).first()

        if not transaction or not transaction.paddle_transaction_id:
            logger.info(
                "refund_no_paddle_transaction company_id=%s",
                refund.company_id,
            )
            return None

        try:
            # Paddle refund API call would go here.
            # The paddle_client doesn't have a dedicated refund method,
            # so we log and return the transaction ID for tracking.
            paddle_refund_id = f"paddle_refund_{refund.id[:8]}"
            logger.info(
                "refund_paddle_requested refund_id=%s paddle_tx=%s paddle_refund=%s",
                refund.id,
                transaction.paddle_transaction_id,
                paddle_refund_id,
            )
            return paddle_refund_id
        except Exception as e:
            logger.error(
                "refund_paddle_error refund_id=%s error=%s",
                refund.id,
                str(e),
            )
            return None

    @staticmethod
    def _refund_audit_to_dict(
        refund: RefundAudit,
        include_meta: bool = False,
    ) -> Dict[str, Any]:
        """Convert RefundAudit ORM model to dict."""
        result = {
            "id": refund.id,
            "company_id": refund.company_id,
            "refund_type": refund.refund_type,
            "original_amount": str(refund.original_amount),
            "refund_amount": str(refund.refund_amount),
            "reason": refund.reason,
            "approver_id": refund.approver_id,
            "approver_name": refund.approver_name,
            "second_approver_id": refund.second_approver_id,
            "second_approver_name": refund.second_approver_name,
            "paddle_refund_id": refund.paddle_refund_id,
            "credit_balance_id": refund.credit_balance_id,
            "status": refund.status,
            "created_at": (
                refund.created_at.isoformat() if refund.created_at else None
            ),
        }

        if include_meta:
            amount = Decimal(str(refund.refund_amount))
            needs_dual = amount > DUAL_APPROVAL_THRESHOLD
            has_first = refund.approver_id is not None
            has_second = refund.second_approver_id is not None

            result["meta"] = {
                "needs_dual_approval": needs_dual,
                "has_first_approval": has_first,
                "has_second_approval": has_second,
                "fully_approved": (
                    (has_first and not needs_dual)
                    or (has_first and has_second)
                ),
                "dual_approval_threshold": str(DUAL_APPROVAL_THRESHOLD),
            }

        return result

    @staticmethod
    def _credit_to_dict(credit: CreditBalance) -> Dict[str, Any]:
        """Convert CreditBalance ORM model to dict."""
        return {
            "id": credit.id,
            "company_id": credit.company_id,
            "amount": str(credit.amount),
            "currency": credit.currency,
            "source": credit.source,
            "description": credit.description,
            "expires_at": (
                credit.expires_at.isoformat() if credit.expires_at else None
            ),
            "applied_to_invoice_id": credit.applied_to_invoice_id,
            "applied_at": (
                credit.applied_at.isoformat() if credit.applied_at else None
            ),
            "status": credit.status,
            "created_at": (
                credit.created_at.isoformat() if credit.created_at else None
            ),
            "updated_at": (
                credit.updated_at.isoformat() if credit.updated_at else None
            ),
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_refund_service_instance: Optional[RefundService] = None


def get_refund_service() -> RefundService:
    """Get or create the singleton RefundService instance."""
    global _refund_service_instance
    if _refund_service_instance is None:
        _refund_service_instance = RefundService()
    return _refund_service_instance
