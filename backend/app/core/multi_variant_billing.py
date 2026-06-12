"""Multi-variant billing service with UNIVERSAL payment architecture.

CRITICAL DESIGN PRINCIPLE:
    Paddle is ONLY for PARWA's own subscription variant billing.
    Clients can use ANY payment provider (Stripe, PayPal, Razorpay, etc.)
    via the integration system. The billing service is provider-agnostic.

Variant routing logic:
    Complexity 1-3 → lowest active variant (Mini → PARWA → High)
    Complexity 4-7 → middle active variant (PARWA → High)
    Complexity 8-10 → PARWA High (must be active)

All money calculations use Decimal (never float).
BC-001: All operations scoped to company_id.
BC-008: Never crash — all external calls wrapped in try/except.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """Raised when payment gateway operations fail."""
    pass


class UniversalPaymentGateway:
    """UNIVERSAL payment gateway — clients can use ANY payment provider.

    Paddle is ONLY used for PARWA's own subscription billing.
    Clients connect their own payment providers (Stripe, PayPal, Razorpay, etc.)
    via the integration system.
    """

    SUPPORTED_PROVIDERS = {"stripe", "paypal", "razorpay", "paddle", "custom"}

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._gateways: Dict[str, Any] = {}

    def register_gateway(self, provider: str, credentials: dict) -> bool:
        """Register a payment provider for this company.

        Args:
            provider: One of stripe, paypal, razorpay, paddle, custom
            credentials: Provider-specific credentials (will be encrypted by caller)

        Returns:
            True if registration succeeded, False otherwise.
        """
        try:
            provider = provider.lower().strip()
            if provider not in self.SUPPORTED_PROVIDERS:
                logger.warning(
                    f"Unsupported payment provider: {provider}. "
                    f"Supported: {self.SUPPORTED_PROVIDERS}"
                )
                return False

            self._gateways[provider] = {
                "credentials": credentials,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "company_id": self.company_id,
            }
            logger.info(
                f"Payment gateway registered: {provider} for company {self.company_id}"
            )
            return True
        except Exception as exc:
            logger.error(f"Failed to register gateway {provider}: {exc}")
            return False

    def process_charge(
        self,
        provider: str,
        amount: Decimal,
        currency: str = "USD",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Process a charge via the specified provider.

        Args:
            provider: Payment provider name
            amount: Charge amount (Decimal, never float)
            currency: ISO currency code
            metadata: Additional charge metadata

        Returns:
            Dict with status, charge_id, and provider details.
            Never raises — returns error dict on failure (BC-008).
        """
        try:
            provider = provider.lower().strip()

            if provider not in self._gateways:
                return {
                    "status": "error",
                    "error": f"Provider {provider} not registered for this company",
                    "charge_id": None,
                }

            if amount <= 0:
                return {
                    "status": "error",
                    "error": "Charge amount must be positive",
                    "charge_id": None,
                }

            gateway = self._gateways[provider]

            # In production, each provider would have a real SDK call here.
            # For now, we create a structured charge record.
            charge_id = f"chg_{provider}_{uuid.uuid4().hex[:12]}"
            charge_record = {
                "charge_id": charge_id,
                "provider": provider,
                "amount": str(amount),
                "currency": currency,
                "status": "processed",
                "company_id": self.company_id,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"Charge processed: {charge_id} via {provider} "
                f"for {amount} {currency} (company: {self.company_id})"
            )
            return charge_record

        except Exception as exc:
            logger.error(f"Charge processing failed via {provider}: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "charge_id": None,
            }

    def get_gateway(self, provider: str) -> Optional[Any]:
        """Get a registered gateway client."""
        return self._gateways.get(provider.lower().strip())

    def list_gateways(self) -> List[str]:
        """List all registered payment providers for this company."""
        return list(self._gateways.keys())

    def unregister_gateway(self, provider: str) -> bool:
        """Unregister a payment provider."""
        try:
            provider = provider.lower().strip()
            if provider in self._gateways:
                del self._gateways[provider]
                logger.info(f"Gateway {provider} unregistered for company {self.company_id}")
                return True
            return False
        except Exception as exc:
            logger.error(f"Failed to unregister gateway {provider}: {exc}")
            return False


class MultiVariantBillingService:
    """Multi-variant billing with UNIVERSAL payment support.

    Paddle is ONLY for PARWA's own subscription variant billing.
    Clients use their own connected payment providers.

    All monetary calculations use Decimal for precision.
    Pure math calculations (calculate_monthly_cost) — no API calls, no AI.
    """

    VARIANT_PRICING = {
        "mini": {
            "price": Decimal("999"),
            "tickets": 500,
            "overage": Decimal("0.10"),
            "label": "Mini PARWA",
        },
        "parwa": {
            "price": Decimal("2499"),
            "tickets": 2000,
            "overage": Decimal("0.10"),
            "label": "PARWA",
        },
        "high": {
            "price": Decimal("4999"),
            "tickets": 5000,
            "overage": Decimal("0.10"),
            "label": "PARWA High",
        },
    }

    ADDON_PRICING = {
        "voice": Decimal("199"),
        "custom_api": Decimal("49"),
    }

    def __init__(self, company_id: str):
        self.company_id = company_id
        self.payment_gateway = UniversalPaymentGateway(company_id)
        self._active_variants: Dict[str, Dict[str, Any]] = {}
        self._addons: List[str] = []

    def route_and_bill(self, complexity_score: int) -> dict:
        """Route ticket to appropriate variant based on complexity score.

        Routing logic:
            1-3: Lowest active variant (Mini → PARWA → High)
            4-7: Middle active variant (PARWA → High)
            8-10: PARWA High (must be active)

        If target variant's ticket limit is reached, route to next higher.
        If ALL limits reached, overage on highest variant.

        Args:
            complexity_score: 1-10 complexity rating

        Returns:
            Dict with routed_variant, complexity, tickets_remaining, overage status.
        """
        try:
            complexity_score = max(1, min(10, complexity_score))

            if not self._active_variants:
                return {
                    "status": "error",
                    "error": "No active variants",
                    "routed_variant": None,
                    "company_id": self.company_id,
                }

            # Determine target variant based on complexity
            variant_order = ["mini", "parwa", "high"]
            active_order = [v for v in variant_order if v in self._active_variants]

            if not active_order:
                return {
                    "status": "error",
                    "error": "No active variants",
                    "routed_variant": None,
                    "company_id": self.company_id,
                }

            if complexity_score <= 3:
                target = active_order[0]  # Lowest active
            elif complexity_score <= 7:
                target = active_order[-1] if len(active_order) == 1 else active_order[1]
            else:
                target = "high" if "high" in self._active_variants else active_order[-1]

            # Check ticket limits — escalate if limit reached
            variant_data = self._active_variants.get(target, {})
            tickets_used = variant_data.get("tickets_used", 0)
            tickets_limit = variant_data.get("tickets_limit", 0)

            if tickets_used >= tickets_limit:
                # Try next higher variant
                current_idx = variant_order.index(target) if target in variant_order else 0
                escalated = False
                for higher in variant_order[current_idx + 1 :]:
                    if higher in self._active_variants:
                        h_data = self._active_variants[higher]
                        if h_data.get("tickets_used", 0) < h_data.get("tickets_limit", 0):
                            target = higher
                            escalated = True
                            break

                if not escalated:
                    # All limits reached — overage on highest
                    target = active_order[-1]

            # Track usage
            if target in self._active_variants:
                self._active_variants[target]["tickets_used"] = (
                    self._active_variants[target].get("tickets_used", 0) + 1
                )

            variant_data = self._active_variants.get(target, {})
            tickets_used = variant_data.get("tickets_used", 0)
            tickets_limit = variant_data.get("tickets_limit", 0)

            return {
                "status": "success",
                "routed_variant": target,
                "complexity_score": complexity_score,
                "tickets_used": tickets_used,
                "tickets_limit": tickets_limit,
                "tickets_remaining": max(0, tickets_limit - tickets_used),
                "overage": tickets_used > tickets_limit,
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Route and bill failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "routed_variant": None,
                "company_id": self.company_id,
            }

    def add_variant(
        self, variant: str, payment_provider: str = "paddle"
    ) -> dict:
        """Add a variant subscription for this company.

        Args:
            variant: One of mini, parwa, high
            payment_provider: Payment provider for this charge.
                Defaults to 'paddle' for PARWA's own subscription billing.
                Clients can specify their own provider (stripe, paypal, etc.)

        Returns:
            Dict with variant details and charge status.
        """
        try:
            variant = variant.lower().strip()
            if variant not in self.VARIANT_PRICING:
                return {
                    "status": "error",
                    "error": f"Unknown variant: {variant}. Must be mini, parwa, or high",
                    "company_id": self.company_id,
                }

            pricing = self.VARIANT_PRICING[variant]

            # Process charge via configured payment gateway
            charge_result = self._process_variant_charge(
                variant=variant,
                payment_provider=payment_provider,
                amount=pricing["price"],
            )

            if charge_result.get("status") == "error":
                return {
                    "status": "error",
                    "error": f"Payment failed: {charge_result.get('error', 'Unknown')}",
                    "variant": variant,
                    "company_id": self.company_id,
                }

            # Activate variant
            self._active_variants[variant] = {
                "tickets_used": 0,
                "tickets_limit": pricing["tickets"],
                "overage_rate": pricing["overage"],
                "price": pricing["price"],
                "label": pricing["label"],
                "activated_at": datetime.now(timezone.utc).isoformat(),
                "payment_provider": payment_provider,
                "charge_id": charge_result.get("charge_id"),
            }

            return {
                "status": "success",
                "variant": variant,
                "price": str(pricing["price"]),
                "tickets_per_month": pricing["tickets"],
                "payment_provider": payment_provider,
                "charge_id": charge_result.get("charge_id"),
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Add variant failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "variant": variant,
                "company_id": self.company_id,
            }

    def remove_variant(self, variant: str) -> dict:
        """Remove a variant (next billing cycle).

        Per D13: Variant downgrade = next cycle. Keep capacity until cycle ends.
        No proration, no partial refund.

        Args:
            variant: Variant to remove

        Returns:
            Dict with removal status.
        """
        try:
            variant = variant.lower().strip()

            if variant not in self._active_variants:
                return {
                    "status": "error",
                    "error": f"Variant {variant} is not active",
                    "company_id": self.company_id,
                }

            variant_data = self._active_variants[variant]
            variant_data["pending_removal"] = True
            variant_data["removal_scheduled_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            return {
                "status": "success",
                "variant": variant,
                "message": f"Variant {variant} will be removed at end of billing cycle",
                "tickets_used": variant_data.get("tickets_used", 0),
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Remove variant failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "company_id": self.company_id,
            }

    def track_usage(self, variant: str, tickets_count: int = 1) -> dict:
        """Track ticket usage against variant limit.

        Args:
            variant: Variant name
            tickets_count: Number of tickets to add

        Returns:
            Dict with usage stats.
        """
        try:
            variant = variant.lower().strip()

            if variant not in self._active_variants:
                return {
                    "status": "error",
                    "error": f"Variant {variant} is not active",
                    "company_id": self.company_id,
                }

            data = self._active_variants[variant]
            data["tickets_used"] = data.get("tickets_used", 0) + tickets_count

            tickets_used = data["tickets_used"]
            tickets_limit = data.get("tickets_limit", 0)
            overage = max(0, tickets_used - tickets_limit)

            return {
                "status": "success",
                "variant": variant,
                "tickets_used": tickets_used,
                "tickets_limit": tickets_limit,
                "tickets_remaining": max(0, tickets_limit - tickets_used),
                "overage_tickets": overage,
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Track usage failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "company_id": self.company_id,
            }

    def get_usage_summary(self) -> dict:
        """Get usage summary across all active variants.

        Returns:
            Dict with per-variant usage and total stats.
        """
        try:
            summary = {}
            total_used = 0
            total_limit = 0

            for variant, data in self._active_variants.items():
                used = data.get("tickets_used", 0)
                limit = data.get("tickets_limit", 0)
                pricing = self.VARIANT_PRICING.get(variant, {})

                summary[variant] = {
                    "tickets_used": used,
                    "tickets_limit": limit,
                    "tickets_remaining": max(0, limit - used),
                    "overage": max(0, used - limit),
                    "overage_rate": str(pricing.get("overage", Decimal("0.10"))),
                    "overage_cost": str(
                        max(0, used - limit) * pricing.get("overage", Decimal("0.10"))
                    ),
                    "pending_removal": data.get("pending_removal", False),
                }
                total_used += used
                total_limit += limit

            return {
                "status": "success",
                "variants": summary,
                "total_tickets_used": total_used,
                "total_tickets_limit": total_limit,
                "total_remaining": max(0, total_limit - total_used),
                "active_variants": list(self._active_variants.keys()),
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Usage summary failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "company_id": self.company_id,
            }

    def calculate_monthly_cost(
        self, variants: List[str], add_ons: Optional[List[str]] = None
    ) -> dict:
        """Calculate monthly cost. Pure math, no API calls, no AI.

        Per D7: Pure JavaScript math on frontend, data from pricing config.
        This backend method provides the same calculation engine.

        Args:
            variants: List of variant names
            add_ons: List of add-on names

        Returns:
            Dict with itemized costs and total.
        """
        try:
            items = []
            total = Decimal("0")

            for variant in variants:
                variant = variant.lower().strip()
                pricing = self.VARIANT_PRICING.get(variant)
                if pricing:
                    items.append(
                        {
                            "type": "variant",
                            "name": pricing["label"],
                            "variant": variant,
                            "price": str(pricing["price"]),
                        }
                    )
                    total += pricing["price"]

            for addon in (add_ons or []):
                addon = addon.lower().strip()
                addon_price = self.ADDON_PRICING.get(addon)
                if addon_price:
                    items.append(
                        {
                            "type": "addon",
                            "name": addon.replace("_", " ").title(),
                            "addon": addon,
                            "price": str(addon_price),
                        }
                    )
                    total += addon_price

            # Calculate savings vs humans (based on $10/ticket human cost)
            total_tickets = sum(
                self.VARIANT_PRICING.get(v, {}).get("tickets", 0) for v in variants
            )
            human_cost = Decimal(str(total_tickets)) * Decimal("10")
            savings = human_cost - total

            return {
                "status": "success",
                "items": items,
                "total_monthly": str(total),
                "total_tickets_per_month": total_tickets,
                "human_cost_equivalent": str(human_cost),
                "savings_vs_human": str(max(Decimal("0"), savings)),
                "currency": "USD",
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Cost calculation failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "company_id": self.company_id,
            }

    def estimate_overage(self, variant: str, projected_tickets: int) -> dict:
        """Estimate overage cost for a variant.

        Args:
            variant: Variant name
            projected_tickets: Expected ticket count

        Returns:
            Dict with overage estimate.
        """
        try:
            variant = variant.lower().strip()
            pricing = self.VARIANT_PRICING.get(variant)

            if not pricing:
                return {
                    "status": "error",
                    "error": f"Unknown variant: {variant}",
                    "company_id": self.company_id,
                }

            included = pricing["tickets"]
            overage_rate = pricing["overage"]
            overage_tickets = max(0, projected_tickets - included)
            overage_cost = Decimal(str(overage_tickets)) * overage_rate

            return {
                "status": "success",
                "variant": variant,
                "tickets_included": included,
                "tickets_projected": projected_tickets,
                "overage_tickets": overage_tickets,
                "overage_rate": str(overage_rate),
                "estimated_overage_cost": str(overage_cost),
                "estimated_total": str(pricing["price"] + overage_cost),
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Overage estimation failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "company_id": self.company_id,
            }

    def _process_variant_charge(
        self, variant: str, payment_provider: str, amount: Decimal
    ) -> dict:
        """Process variant subscription charge via configured payment gateway.

        Uses Paddle for PARWA's own subscription billing.
        Uses client's connected provider for their charges.
        3-strategy resolution:
            1. Try registered gateway for the specified provider
            2. Try PaddleService for PARWA's own billing
            3. Return pending status with manual processing message

        Args:
            variant: Variant name
            payment_provider: Payment provider to use
            amount: Charge amount

        Returns:
            Dict with charge status.
        """
        try:
            # Strategy 1: Try registered gateway
            if payment_provider in self.payment_gateway.list_gateways():
                result = self.payment_gateway.process_charge(
                    provider=payment_provider,
                    amount=amount,
                    currency="USD",
                    metadata={
                        "variant": variant,
                        "company_id": self.company_id,
                        "type": "variant_subscription",
                    },
                )
                if result.get("status") == "processed":
                    return result

            # Strategy 2: Try Paddle for PARWA's own billing
            try:
                paddle_result = self.payment_gateway.process_charge(
                    provider="paddle",
                    amount=amount,
                    currency="USD",
                    metadata={
                        "variant": variant,
                        "company_id": self.company_id,
                        "type": "variant_subscription",
                        "provider": "paddle",
                    },
                )
                if paddle_result.get("status") == "processed":
                    return paddle_result
            except Exception:
                pass  # Paddle not available, try next

            # Strategy 3: Return pending status
            logger.warning(
                f"No payment gateway available for variant charge. "
                f"Variant: {variant}, Amount: {amount}, "
                f"Company: {self.company_id}. Marking as pending."
            )
            return {
                "status": "pending",
                "message": "No payment gateway configured. Manual processing required.",
                "variant": variant,
                "amount": str(amount),
                "currency": "USD",
                "charge_id": f"pending_{uuid.uuid4().hex[:12]}",
                "company_id": self.company_id,
            }

        except Exception as exc:
            logger.error(f"Variant charge processing failed: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "charge_id": None,
            }
