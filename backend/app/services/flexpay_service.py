"""
FlexPay Service — Smart Installment Payment Processing

Implements the "FlexPay" payment model:
- Base charge: $100/day (all tiers)
- Extra charge: Additional $100 every 3rd day (PARWA HIGH ONLY - 1 hour after base)
- Completes full subscription amount within 30-day billing cycle
- Stays under Razorpay's $100/transaction limit
- Handles multiple customers simultaneously

Business Rules (2 tiers only — Mini removed):
- PARWA ($2,999): 30 days, $100/day, last day = $99
- PARWA High ($3,999): 30 days with accelerated every-3rd-day double charge, last day = $99

IMPORTANT: The extra charge (every 3rd day: $100 + $100) ONLY applies to PARWA HIGH.
PARWA tier uses standard daily $100 charges only.

CLAUDE.md Compliance:
- P-003: Simple language in docstrings/comments
- P-004: Business-first decisions (revenue protection, customer experience)
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.pricing_config import VariantType, VARIANT_PRICES
from database.models.flexpay import (
    FlexPayPlan, FlexPayInstallment, FlexPayStatus, InstallmentStatus
)
from database.models.billing import Invoice, Transaction

logger = logging.getLogger("parwa.services.flexpay")

# Constants matching business requirements
BASE_INSTALLMENT_AMOUNT = Decimal("100.00")  # $100 base charge
EXTRA_INSTALLMENT_AMOUNT = Decimal("100.00")  # $100 extra on every 3rd day
EXTRA_DAY_INTERVAL = 3  # Add extra charge every 3rd day
EXTRA_CHARGE_DELAY_HOURS = 2  # Extra charge happens 2 hours after base
MAX_CONSECUTIVE_FAILURES = 3  # Pause plan after this many failures
RETRY_DELAY_HOURS = 24  # Retry failed payment after 24 hours


class FlexPayError(Exception):
    """Base exception for FlexPay operations."""
    pass


class FlexPayPlanNotFoundError(FlexPayError):
    """Raised when a plan doesn't exist."""
    pass


class FlexPayInvalidStateError(FlexPayError):
    """Raised when operation invalid for current state."""
    pass


def calculate_installment_schedule(
    total_amount: Decimal,
    variant_tier: str,
    period_start: datetime,
    period_end: datetime
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Calculate the installment schedule for a subscription.
    
    Business Logic:
    - Every day: Charge BASE_INSTALLMENT_AMOUNT ($100)
    - Every EXTRA_DAY_INTERVAL (3rd) day: Charge extra $100 (2 hours later)
    - Final day: Adjust to hit exact total_amount
    
    Args:
        total_amount: Full subscription price ($2999 or $3999)
        variant_tier: Which plan tier (parwa or high)
        period_start: When billing period starts
        period_end: When billing period ends (should be ~30 days later)
    
    Returns:
        Tuple of (list of installment dicts, total number of installments)
    
    Example Output for $3,999:
        [
            {"day": 1, "amount": 100.00, "is_extra": False, "scheduled_at": "..."},
            {"day": 2, "amount": 100.00, "is_extra": False, "scheduled_at": "..."},
            {"day": 3, "amount": 100.00, "is_extra": False, "scheduled_at": "..."},
            {"day": 3, "amount": 100.00, "is_extra": True,  "scheduled_at": "...+2hrs"},
            ...
        ]
    """
    installments = []
    current_date = period_start
    day_number = 1
    collected = Decimal("0")
    total_days = (period_end - period_start).days
    
    while collected < total_amount and day_number <= total_days + 5:  # Buffer days
        # Base charge for this day
        base_amount = min(BASE_INSTALLMENT_AMOUNT, total_amount - collected)
        
        if base_amount > 0:
            installments.append({
                "day": day_number,
                "amount": float(base_amount),
                "is_extra": False,
                "scheduled_at": current_date.replace(hour=9, minute=0, second=0)  # 9 AM
            })
            collected += base_amount
        
        # Extra charge every 3rd day - ONLY for PARWA HIGH tier ($3,999)
        # This accelerates collection to complete in ~30 days instead of 40
        if (variant_tier == "high" and 
            day_number % EXTRA_DAY_INTERVAL == 0 and 
            collected < total_amount):
            extra_amount = min(EXTRA_INSTALLMENT_AMOUNT, total_amount - collected)
            
            if extra_amount > 0:
                # Schedule 1 hour after the base charge (user requested 1hr gap)
                extra_time = current_date.replace(hour=9, minute=0, second=0) + timedelta(hours=1)  # Changed from 2hrs to 1hr
                
                installments.append({
                    "day": day_number,
                    "amount": float(extra_amount),
                    "is_extra": True,
                    "scheduled_at": extra_time,
                    "note": "PARWA HIGH accelerated payment"
                })
                collected += extra_amount
                logger.info(f"PARWA HIGH: Added extra ${extra_amount} installment for day {day_number}")
        
        current_date += timedelta(days=1)
        day_number += 1
        
        # Safety break to prevent infinite loops
        if len(installments) > 60:  # Max ~30 days * 2 charges
            logger.warning("Too many installments calculated, breaking loop")
            break
    
    # Adjust final installment to match exact total
    if installments:
        current_total = sum(Decimal(str(inst["amount"])) for inst in installments)
        difference = total_amount - current_total
        
        if abs(difference) > Decimal("0.01"):  # More than 1 cent difference
            # Adjust last installment
            last_installment = installments[-1]
            new_last_amount = Decimal(str(last_installment["amount"])) + difference
            
            if new_last_amount > 0:
                last_installment["amount"] = float(new_last_amount)
            else:
                # If adjustment makes it negative or zero, remove it
                installments.pop()
    
    return installments, len(installments)


async def create_flexpay_plan(
    db: Session,
    company_id: str,
    user_id: str,
    variant_tier: VariantType,
    razorpay_customer_id: Optional[str] = None,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Create a new FlexPay installment plan for a subscription.
    
    This is called when a customer chooses the "FlexPay" option at checkout.
    Creates the plan and all installment records, but doesn't charge anything yet.
    
    Args:
        db: Database session
        company_id: Company ID from auth
        user_id: User who is purchasing
        variant_tier: Which plan they're buying (parwa/high)
        razorpay_customer_id: Pre-created Razorpay customer (if available)
        period_days: Billing period length (default 30 days)
    
    Returns:
        Dict with plan details including installment schedule
    
    Raises:
        FlexPayError: If plan creation fails
    """
    try:
        # Get price for this variant
        total_amount = Decimal(str(VARIANT_PRICES[variant_tier]))
        
        # Calculate period dates
        period_start = datetime.now(timezone.utc)
        period_end = period_start + timedelta(days=period_days)
        
        # Generate installment schedule
        installment_schedule, total_installments = calculate_installment_schedule(
            total_amount=total_amount,
            variant_tier=variant_tier.value,
            period_start=period_start,
            period_end=period_end
        )
        
        if not installment_schedule:
            raise FlexPayError("Could not generate installment schedule")
        
        # Create the plan record
        plan = FlexPayPlan(
            company_id=company_id,
            user_id=user_id,
            variant_tier=variant_tier.value,
            total_amount=total_amount,
            installment_amount=BASE_INSTALLMENT_AMOUNT,
            extra_installment_amount=EXTRA_INSTALLMENT_AMOUNT,
            total_installments=len(installment_schedule),
            status=FlexPayStatus.PENDING.value,
            current_period_start=period_start,
            current_period_end=period_end,
            razorpay_customer_id=razorpay_customer_id,
        )
        
        db.add(plan)
        db.flush()  # Get plan.id without committing yet
        
        # Create all installment records
        for idx, inst_data in enumerate(installment_schedule, start=1):
            installment = FlexPayInstallment(
                plan_id=plan.id,
                company_id=company_id,
                installment_number=idx,
                amount=Decimal(str(inst_data["amount"])),
                is_extra=inst_data["is_extra"],
                status=InstallmentStatus.PENDING.value,
                scheduled_at=inst_data["scheduled_at"],
            )
            db.add(installment)
        
        db.commit()
        
        logger.info(
            f"Created FlexPay plan {plan.id[:8]}... for company {company_id}, "
            f"variant={variant_tier.value}, total=${total_amount}, "
            f"{len(installment_schedule)} installments over {period_days} days"
        )
        
        return {
            "plan_id": plan.id,
            "variant_tier": variant_tier.value,
            "total_amount": float(total_amount),
            "total_installments": len(installment_schedule),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "status": plan.status,
            "installment_schedule": [
                {
                    "number": i + 1,
                    "amount": inst["amount"],
                    "is_extra": inst["is_extra"],
                    "scheduled_at": inst["scheduled_at"].isoformat() if hasattr(inst["scheduled_at"], 'isoformat') else str(inst["scheduled_at"])
                }
                for i, inst in enumerate(installment_schedule)
            ]
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create FlexPay plan: {e}")
        raise FlexPayError(f"Plan creation failed: {str(e)}")


async def process_next_installment(
    db: Session,
    plan_id: str,
    razorpay_client=None  # Will be injected
) -> Dict[str, Any]:
    """
    Process the next pending installment for a FlexPay plan.
    
    Called by:
    1. The cron job scheduler (daily/hourly)
    2. Immediately after first payment authorization
    
    Args:
        db: Database session
        plan_id: Plan to process
        razorpay_client: Razorpay client instance (for actual charging)
    
    Returns:
        Dict with processing result
    
    Raises:
        FlexPayPlanNotFoundError: Plan doesn't exist
        FlexPayInvalidStateError: Plan not in processable state
    """
    # Get plan
    plan = db.query(FlexPayPlan).filter(FlexPayPlan.id == plan_id).first()
    if not plan:
        raise FlexPayPlanNotFoundError(f"Plan {plan_id} not found")
    
    # Check plan is in valid state for processing
    valid_statuses = [FlexPayStatus.PENDING.value, FlexPayStatus.ACTIVE.value]
    if plan.status not in valid_statuses:
        raise FlexPayInvalidStateError(
            f"Plan {plan_id} is in {plan.status} state, cannot process"
        )
    
    # Find next pending installment
    next_installment = db.query(FlexPayInstallment).filter(
        FlexPayInstallment.plan_id == plan_id,
        FlexPayInstallment.status == InstallmentStatus.PENDING.value
    ).order_by(FlexPayInstallment.installment_number.asc()).first()
    
    if not next_installment:
        # No more pending installments - check if all paid
        all_installments = db.query(FlexPayInstallment).filter(
            FlexPayInstallment.plan_id == plan_id
        ).all()
        
        paid_count = sum(1 for i in all_installments if i.status == InstallmentStatus.PAID.value)
        
        if paid_count == plan.total_installments:
            # All done!
            plan.status = FlexPayStatus.COMPLETED.value
            plan.completed_at = datetime.now(timezone.utc)
            db.commit()
            
            return {
                "status": "completed",
                "plan_id": plan_id,
                "message": "All installments paid successfully"
            }
        else:
            # Some failed/skipped
            return {
                "status": "no_pending",
                "plan_id": plan_id,
                "message": "No pending installments remaining"
            }
    
    # Process this installment
    try:
        # Update status to processing
        next_installment.status = InstallmentStatus.PROCESSING.value
        db.commit()
        
        # ACTUAL CHARGING WOULD HAPPEN HERE
        # For now, simulate success (will integrate with Razorpay client later)
        if razorpay_client:
            # TODO: Implement actual Razorpay charging
            # result = await razorpay_client.charge_tokenized_card(
            #     customer_id=plan.razorpay_customer_id,
            #     amount=int(next_installment.amount * 100),  # Convert to cents
            #     currency="USD",
            #     description=f"FlexPay #{next_installment.installment_number}"
            # )
            payment_id = f"pay_simulated_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            payment_success = True
        else:
            # Simulate success for testing
            payment_id = f"pay_simulated_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            payment_success = True
        
        if payment_success:
            # Mark as paid
            next_installment.status = InstallmentStatus.PAID.value
            next_installment.razorpay_payment_id = payment_id
            next_installment.processed_at = datetime.now(timezone.utc)
            
            # Update plan
            plan.completed_installments += 1
            plan.consecutive_failures = 0  # Reset failure count
            plan.last_failure_reason = None
            plan.last_failure_at = None
            
            if plan.status == FlexPayStatus.PENDING.value:
                plan.status = FlexPayStatus.ACTIVE.value
            
            # Create invoice record
            db.add(Invoice(
                company_id=plan.company_id,
                paddle_invoice_id=payment_id,
                amount=next_installment.amount,
                currency="USD",
                status="paid",
                invoice_date=datetime.now(timezone.utc),
                paid_at=datetime.now(timezone.utc),
            ))
            
            # Create transaction record
            db.add(Transaction(
                company_id=plan.company_id,
                paddle_transaction_id=payment_id,
                amount=next_installment.amount,
                currency="USD",
                status="completed",
                transaction_type="flexpay_installment",
                description=f"FlexPay installment #{next_installment.installment_number} for {plan.variant_tier}",
            ))
            
            db.commit()
            
            logger.info(
                f"Processed FlexPay installment #{next_installment.installment_number} "
                f"for plan {plan_id[:8]}..., amount=${next_installment.amount}"
            )
            
            return {
                "status": "success",
                "plan_id": plan_id,
                "installment_number": next_installment.installment_number,
                "amount": float(next_installment.amount),
                "payment_id": payment_id,
                "remaining": plan.total_installments - plan.completed_installments
            }
        else:
            # Payment failed
            return _handle_installment_failure(db, plan, next_installment, "Payment declined")
            
    except Exception as e:
        db.rollback()
        return _handle_installment_failure(db, plan, next_installment, str(e))


def _handle_installment_failure(
    db: Session,
    plan: FlexPayPlan,
    installment: FlexPayInstallment,
    reason: str
) -> Dict[str, Any]:
    """Handle a failed installment with retry logic."""
    
    installment.status = InstallmentStatus.FAILED.value
    installment.failure_reason = reason
    installment.retry_count += 1
    installment.retry_after = datetime.now(timezone.utc) + timedelta(hours=RETRY_DELAY_HOURS)
    
    # Update plan failure tracking
    plan.consecutive_failures += 1
    plan.last_failure_reason = reason
    plan.last_failure_at = datetime.now(timezone.utc)
    
    # Check if we should pause the plan
    if plan.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        plan.status = FlexPayStatus.PAUSED.value
        
        logger.warning(
            f"FlexPay plan {plan.id[:8]}... PAUSED after {MAX_CONSECUTIVE_FAILURES} consecutive failures"
        )
    else:
        logger.warning(
            f"FlexPay installment #{installment.installment_number} failed "
            f"(attempt {installment.retry_count}/{MAX_CONSECUTIVE_FAILURES}): {reason}"
        )
    
    db.commit()
    
    return {
        "status": "failed",
        "plan_id": plan.id,
        "installment_number": installment.installment_number,
        "reason": reason,
        "retry_count": installment.retry_count,
        "plan_paused": plan.status == FlexPayStatus.PAUSED.value
    }


async def get_plan_status(db: Session, plan_id: str) -> Dict[str, Any]:
    """Get current status of a FlexPay plan with progress details."""
    
    plan = db.query(FlexPayPlan).filter(FlexPayPlan.id == plan_id).first()
    if not plan:
        raise FlexPayPlanNotFoundError(f"Plan {plan_id} not found")
    
    # Get installment summary
    installments = db.query(FlexPayInstallment).filter(
        FlexPayInstallment.plan_id == plan_id
    ).order_by(FlexPayInstallment.installment_number.asc()).all()
    
    paid_amount = sum(i.amount for i in installments if i.status == InstallmentStatus.PAID.value)
    pending_amount = sum(i.amount for i in installments if i.status == InstallmentStatus.PENDING.value)
    failed_amount = sum(i.amount for i in installments if i.status == InstallmentStatus.FAILED.value)
    
    return {
        "plan_id": plan.id,
        "variant_tier": plan.variant_tier,
        "status": plan.status,
        "total_amount": float(plan.total_amount),
        "collected_amount": float(paid_amount),
        "remaining_amount": float(pending_amount),
        "progress_percent": float((paid_amount / plan.total_amount) * 100) if plan.total_amount > 0 else 0,
        "installments": {
            "total": plan.total_installments,
            "completed": plan.completed_installments,
            "pending": len([i for i in installments if i.status == InstallmentStatus.PENDING.value]),
            "failed": len([i for i in installments if i.status == InstallmentStatus.FAILED.value]),
        },
        "period": {
            "start": plan.current_period_start.isoformat() if plan.current_period_start else None,
            "end": plan.current_period_end.isoformat() if plan.current_period_end else None,
        },
        "failure_info": {
            "consecutive_failures": plan.consecutive_failures,
            "last_reason": plan.last_failure_reason,
            "last_failure_at": plan.last_failure_at.isoformat() if plan.last_failure_at else None,
        } if plan.consecutive_failures > 0 else None,
        "recent_installments": [
            {
                "number": i.installment_number,
                "amount": float(i.amount),
                "status": i.status,
                "processed_at": i.processed_at.isoformat() if i.processed_at else None,
            }
            for i in installments[-5:]  # Last 5 installments
        ]
    }


async def cancel_flexpay_plan(
    db: Session,
    plan_id: str,
    reason: str = "Customer requested cancellation"
) -> Dict[str, Any]:
    """Cancel a FlexPay plan and mark remaining installments as skipped."""
    
    plan = db.query(FlexPayPlan).filter(FlexPayPlan.id == plan_id).first()
    if not plan:
        raise FlexPayPlanNotFoundError(f"Plan {plan_id} not found")
    
    if plan.status in [FlexPayStatus.COMPLETED.value, FlexPayStatus.CANCELLED.value]:
        raise FlexPayInvalidStateError(f"Cannot cancel plan in {plan.status} state")
    
    # Mark pending installments as skipped
    pending_installments = db.query(FlexPayInstallment).filter(
        FlexPayInstallment.plan_id == plan_id,
        FlexPayInstallment.status == InstallmentStatus.PENDING.value
    ).all()
    
    for installment in pending_installments:
        installment.status = InstallmentStatus.SKIPPED.value
    
    # Update plan
    plan.status = FlexPayStatus.CANCELLED.value
    plan.cancelled_at = datetime.now(timezone.utc)
    plan.notes = reason
    
    db.commit()
    
    logger.info(f"Cancelled FlexPay plan {plan_id[:8]}..., reason: {reason}")
    
    return {
        "status": "cancelled",
        "plan_id": plan_id,
        "skipped_installments": len(pending_installments),
        "collected_amount": float(sum(
            i.amount for i in db.query(FlexPayInstallment).filter(
                FlexPayInstallment.plan_id == plan_id,
                FlexPayInstallment.status == InstallmentStatus.PAID.value
            ).all()
        ))
    }


async def get_due_installments(db: Session, hours_ahead: int = 1) -> List[Dict[str, Any]]:
    """
    Find all installments that are due for processing.
    
    Used by the cron job scheduler to batch-process payments.
    
    Args:
        db: Database session
        hours_ahead: How far ahead to look for due installments
    
    Returns:
        List of dicts with plan/installment info for processing
    """
    now = datetime.now(timezone.utc)
    look_ahead = now + timedelta(hours=hours_ahead)
    
    # Only get installments from ACTIVE or PENDING plans
    due_installments = db.query(FlexPayInstallment).join(
        FlexPayPlan, FlexPayInstallment.plan_id == FlexPayPlan.id
    ).filter(
        FlexPayInstallment.status == InstallmentStatus.PENDING.value,
        FlexPayInstallment.scheduled_at <= look_ahead,
        FlexPayInstallment.scheduled_at > now - timedelta(hours=1),  # Don't reprocess old ones
        FlexPayPlan.status.in_([FlexPayStatus.ACTIVE.value, FlexPayStatus.PENDING.value])
    ).order_by(FlexPayInstallment.scheduled_at.asc()).all()
    
    return [
        {
            "installment_id": inst.id,
            "plan_id": inst.plan_id,
            "company_id": inst.company_id,
            "installment_number": inst.installment_number,
            "amount": float(inst.amount),
            "is_extra": inst.is_extra,
            "scheduled_at": inst.scheduled_at.isoformat(),
            "variant_tier": inst.plan.variant_tier if inst.plan else "unknown"
        }
        for inst in due_installments
    ]


async def pause_flexpay_plan(
    db: Session,
    plan_id: str,
    reason: str = "Payment failure - auto-paused"
) -> Dict[str, Any]:
    """
    Pause a FlexPay plan.
    
    Stops all future installment processing until manually resumed.
    Usually triggered by multiple payment failures or manual admin action.
    
    Args:
        db: Database session
        plan_id: Plan to pause
        reason: Why the plan is being paused
    
    Returns:
        Dict with pause details
    
    Raises:
        FlexPayPlanNotFoundError: Plan doesn't exist
        FlexPayInvalidStateError: Plan not in pausable state
    """
    plan = db.query(FlexPayPlan).filter(FlexPayPlan.id == plan_id).first()
    
    if not plan:
        raise FlexPayPlanNotFoundError(f"Plan {plan_id} not found")
    
    if plan.status not in [FlexPayStatus.PENDING.value, FlexPayStatus.ACTIVE.value]:
        raise FlexPayInvalidStateError(
            f"Cannot pause plan in {plan.status} state. Only pending/active plans can be paused."
        )
    
    # Update plan status
    old_status = plan.status
    plan.status = FlexPayStatus.PAUSED.value
    plan.notes = f"Paused: {reason}"
    
    # Count pending installments that will be affected
    pending_count = db.query(FlexPayInstallment).filter(
        FlexPayInstallment.plan_id == plan_id,
        FlexPayInstallment.status == InstallmentStatus.PENDING.value
    ).count()
    
    db.commit()
    
    logger.warning(
        f"FlexPay plan {plan_id[:8]}... PAUSED (was {old_status}). "
        f"Reason: {reason}. {pending_count} installments affected."
    )
    
    return {
        "status": "paused",
        "plan_id": plan_id,
        "previous_status": old_status,
        "reason": reason,
        "pending_installments": pending_count,
        "paused_at": datetime.now(timezone.utc).isoformat()
    }


async def resume_flexpay_plan(
    db: Session,
    plan_id: str,
    notes: str = "Customer resumed payment"
) -> Dict[str, Any]:
    """
    Resume a paused FlexPay plan.
    
    Restarts installment processing from where it left off.
    Resets failure counters for a fresh start.
    
    Args:
        db: Database session
        plan_id: Plan to resume
        notes: Notes about the resume action
    
    Returns:
        Dict with resume details
    
    Raises:
        FlexPayPlanNotFoundError: Plan doesn't exist
        FlexPayInvalidStateError: Plan not in paused state
    """
    plan = db.query(FlexPayPlan).filter(FlexPayPlan.id == plan_id).first()
    
    if not plan:
        raise FlexPayPlanNotFoundError(f"Plan {plan_id} not found")
    
    if plan.status != FlexPayStatus.PAUSED.value:
        raise FlexPayInvalidStateError(
            f"Cannot resume plan in {plan.status} state. Only paused plans can be resumed."
        )
    
    # Reset failure tracking
    plan.status = FlexPayStatus.ACTIVE.value
    plan.consecutive_failures = 0
    plan.last_failure_reason = None
    plan.last_failure_at = None
    plan.notes = f"Resumed: {notes}"
    
    # Find next pending installment
    next_installment = db.query(FlexPayInstallment).filter(
        FlexPayInstallment.plan_id == plan_id,
        FlexPayInstallment.status == InstallmentStatus.PENDING.value
    ).order_by(FlexPayInstallment.installment_number.asc()).first()
    
    # Calculate remaining amount
    pending_installments = db.query(FlexPayInstallment).filter(
        FlexPayInstallment.plan_id == plan_id,
        FlexPayInstallment.status == InstallmentStatus.PENDING.value
    ).all()
    
    remaining_amount = sum(inst.amount for inst in pending_installments)
    
    # Calculate time until next installment
    next_in = None
    if next_installment and next_installment.scheduled_at:
        now = datetime.now(timezone.utc)
        delta = next_installment.scheduled_at - now
        total_seconds = delta.total_seconds()
        
        if total_seconds > 0:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            next_in = f"{hours}h {minutes}m" if hours > 0 else f"{minutes} minutes"
        else:
            next_in = "due now"
    
    db.commit()
    
    logger.info(
        f"FlexPay plan {plan_id[:8]}... RESUMED. "
        f"Next installment #{next_installment.installment_number if next_installment else 'unknown'} "
        f"in {next_in}. ${remaining_amount:.2f} remaining."
    )
    
    return {
        "status": "active",
        "plan_id": plan_id,
        "notes": notes,
        "next_installment_number": next_installment.installment_number if next_installment else None,
        "next_installment_in": next_in,
        "remaining_amount": float(remaining_amount),
        "resumed_at": datetime.now(timezone.utc).isoformat()
    }
