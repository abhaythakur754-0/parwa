"""
PARWA Pricing Service (Day 6)

Business logic for pricing calculations and variant management.

This is a simple service that could be extended to:
- Store pricing in database for dynamic updates
- Apply discounts and promotions
- Track pricing history
- Support custom enterprise pricing
"""

from typing import Dict, List, Optional

# Re-export constants from pricing API for service use
VALID_INDUSTRIES = ["ecommerce", "saas", "logistics", "others"]

INDUSTRY_VARIANTS = {
    "ecommerce": [
        {
            "id": "ecom-order",
            "name": "Order Management",
            "tickets_per_month": 500,
            "price_per_month": 99,
            "popular": True,
        },
        {
            "id": "ecom-returns",
            "name": "Returns & Refunds",
            "tickets_per_month": 200,
            "price_per_month": 49,
            "popular": False,
        },
        {
            "id": "ecom-product",
            "name": "Product FAQ",
            "tickets_per_month": 1000,
            "price_per_month": 79,
            "popular": False,
        },
        {
            "id": "ecom-shipping",
            "name": "Shipping Inquiries",
            "tickets_per_month": 300,
            "price_per_month": 59,
            "popular": False,
        },
        {
            "id": "ecom-payment",
            "name": "Payment Issues",
            "tickets_per_month": 150,
            "price_per_month": 39,
            "popular": False,
        },
    ],
    "saas": [
        {
            "id": "saas-tech",
            "name": "Technical Support",
            "tickets_per_month": 400,
            "price_per_month": 129,
            "popular": True,
        },
        {
            "id": "saas-billing",
            "name": "Billing Support",
            "tickets_per_month": 200,
            "price_per_month": 69,
            "popular": False,
        },
        {
            "id": "saas-feature",
            "name": "Feature Requests",
            "tickets_per_month": 300,
            "price_per_month": 89,
            "popular": False,
        },
        {
            "id": "saas-api",
            "name": "API Support",
            "tickets_per_month": 250,
            "price_per_month": 99,
            "popular": False,
        },
        {
            "id": "saas-account",
            "name": "Account Issues",
            "tickets_per_month": 350,
            "price_per_month": 79,
            "popular": False,
        },
    ],
    "logistics": [
        {
            "id": "log-track",
            "name": "Tracking",
            "tickets_per_month": 800,
            "price_per_month": 89,
            "popular": True,
        },
        {
            "id": "log-delivery",
            "name": "Delivery Issues",
            "tickets_per_month": 400,
            "price_per_month": 69,
            "popular": False,
        },
        {
            "id": "log-warehouse",
            "name": "Warehouse Queries",
            "tickets_per_month": 300,
            "price_per_month": 59,
            "popular": False,
        },
        {
            "id": "log-fleet",
            "name": "Fleet Management",
            "tickets_per_month": 200,
            "price_per_month": 79,
            "popular": False,
        },
        {
            "id": "log-customs",
            "name": "Customs & Documentation",
            "tickets_per_month": 150,
            "price_per_month": 99,
            "popular": False,
        },
    ],
    "others": [
        {
            "id": "other-general",
            "name": "General Support",
            "tickets_per_month": 500,
            "price_per_month": 79,
            "popular": True,
        },
        {
            "id": "other-email",
            "name": "Email Support",
            "tickets_per_month": 300,
            "price_per_month": 49,
            "popular": False,
        },
        {
            "id": "other-chat",
            "name": "Chat Support",
            "tickets_per_month": 400,
            "price_per_month": 69,
            "popular": False,
        },
        {
            "id": "other-phone",
            "name": "Phone Support",
            "tickets_per_month": 200,
            "price_per_month": 89,
            "popular": False,
        },
    ],
}


def get_variant_by_id(industry: str, variant_id: str) -> Optional[Dict]:
    """Get a specific variant by industry and ID.

    Args:
        industry: Industry identifier
        variant_id: Variant identifier

    Returns:
        Variant dict or None if not found
    """
    if industry not in INDUSTRY_VARIANTS:
        return None

    for variant in INDUSTRY_VARIANTS[industry]:
        if variant["id"] == variant_id:
            return variant

    return None


def validate_variant_selection(
    industry: str,
    selections: List[Dict[str, int]],
) -> Dict[str, any]:
    """Validate variant selections for an industry.

    Args:
        industry: Industry identifier
        selections: List of {id, quantity} dicts

    Returns:
        Dict with:
        - valid: bool
        - errors: List of error messages
        - validated: List of validated selections with variant info
    """
    errors = []
    validated = []

    if industry not in VALID_INDUSTRIES:
        return {
            "valid": False,
            "errors": [f"Invalid industry: {industry}"],
            "validated": [],
        }

    industry_variants = {v["id"]: v for v in INDUSTRY_VARIANTS.get(industry, [])}

    for selection in selections:
        variant_id = selection.get("id")
        quantity = selection.get("quantity", 0)

        # Validate variant exists
        if variant_id not in industry_variants:
            errors.append(f"Variant '{variant_id}' not found in industry '{industry}'")
            continue

        # Validate quantity
        if not isinstance(quantity, int) or quantity < 0:
            errors.append(f"Invalid quantity for variant '{variant_id}': {quantity}")
            continue

        if quantity > 10:
            errors.append(f"Quantity for variant '{variant_id}' exceeds maximum (10)")
            continue

        if quantity > 0:
            variant = industry_variants[variant_id]
            validated.append(
                {
                    "id": variant_id,
                    "name": variant["name"],
                    "quantity": quantity,
                    "tickets_per_month": variant["tickets_per_month"] * quantity,
                    "price_per_month": variant["price_per_month"] * quantity,
                }
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "validated": validated,
    }


def calculate_totals(
    validated_selections: List[Dict],
) -> Dict[str, int]:
    """Calculate pricing totals from validated selections.

    Args:
        validated_selections: List of validated variant selections

    Returns:
        Dict with total_tickets, total_monthly, annual_cost, annual_savings
    """
    total_tickets = sum(s["tickets_per_month"] for s in validated_selections)
    total_monthly = sum(s["price_per_month"] for s in validated_selections)

    # Annual pricing: 10 months (2 months free)
    annual_cost = total_monthly * 10
    annual_savings = total_monthly * 2

    return {
        "total_tickets": total_tickets,
        "total_monthly": total_monthly,
        "annual_cost": annual_cost,
        "annual_savings": annual_savings,
    }


def get_cheapest_variant(industry: str) -> Optional[Dict]:
    """Get the cheapest variant for an industry.

    Args:
        industry: Industry identifier

    Returns:
        Cheapest variant dict or None
    """
    if industry not in INDUSTRY_VARIANTS:
        return None

    variants = INDUSTRY_VARIANTS[industry]
    if not variants:
        return None

    return min(variants, key=lambda v: v["price_per_month"])


def get_popular_variant(industry: str) -> Optional[Dict]:
    """Get the popular/recommended variant for an industry.

    Args:
        industry: Industry identifier

    Returns:
        Popular variant dict or None
    """
    if industry not in INDUSTRY_VARIANTS:
        return None

    for variant in INDUSTRY_VARIANTS[industry]:
        if variant.get("popular"):
            return variant

    # Fallback to first variant if none marked as popular
    return INDUSTRY_VARIANTS[industry][0] if INDUSTRY_VARIANTS[industry] else None
