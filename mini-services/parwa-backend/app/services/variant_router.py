"""Multi-variant ticket routing service (PHASE 14)."""
from sqlalchemy.orm import Session
from app.models import AIVariant


# Variant priority order (lowest to highest)
VARIANT_PRIORITY = ["mini", "parwa", "parwa_high"]


def route_ticket(tenant_id: str, intent: str, complexity_score: int, db: Session) -> AIVariant:
    """
    Route a ticket to the appropriate variant based on complexity score.
    
    Logic:
    1. Score 1-3: Route to lowest active variant (mini > parwa > parwa_high)
    2. Score 4-7: Route to middle variant (parwa > parwa_high)
    3. Score 8-10: Route to parwa_high (must be active)
    4. If target variant ticket limit reached -> escalate to next variant
    5. If ALL limits reached -> overage on highest variant
    """
    # Get all active variants for tenant
    variants = (
        db.query(AIVariant)
        .filter(
            AIVariant.tenant_id == tenant_id,
            AIVariant.status == "active",
        )
        .all()
    )

    if not variants:
        raise ValueError(f"No active variants found for tenant {tenant_id}")

    # Sort by priority
    active_types = {v.variant_type: v for v in variants}

    # Determine target variant based on complexity score
    if complexity_score <= 3:
        target_order = ["mini", "parwa", "parwa_high"]
    elif complexity_score <= 7:
        target_order = ["parwa", "parwa_high"]
    else:
        target_order = ["parwa_high"]

    # Try to route to the first available variant in the target order
    for variant_type in target_order:
        variant = active_types.get(variant_type)
        if variant:
            # Check if ticket limit is reached
            if variant.tickets_used < variant.ticket_limit:
                # Route here
                variant.tickets_used += 1
                db.commit()
                db.refresh(variant)
                return variant

    # All limits reached in target order - escalate to highest active variant (overage)
    for variant_type in reversed(VARIANT_PRIORITY):
        variant = active_types.get(variant_type)
        if variant:
            variant.tickets_used += 1
            db.commit()
            db.refresh(variant)
            return variant

    # Fallback - return the first available variant
    return variants[0]
