"""
Variant Add-On Service (Day 3: V1–V10)

Manages industry variant add-ons (ecommerce, saas, logistics, others) that
stack ticket and KB doc allocations on top of base plan limits.

Lifecycle:
  ACTIVE   → INACTIVE   (user removes; debited at period end)
  INACTIVE → ARCHIVED   (period-end cron archives + removes Paddle item)
  ARCHIVED → ACTIVE     (user restores; creates new Paddle item)

All money calculations use Decimal (BC-002).
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from database.base import SessionLocal
from database.models.billing import Subscription
from database.models.billing_extended import CompanyVariant, ProrationAudit
from app.schemas.billing import (
    INDUSTRY_ADD_ONS,
    VARIANT_LIMITS,
    CompanyVariantInfo,
    EffectiveLimitsInfo,
    VariantType,
)
from app.clients.paddle_client import PaddleClient, PaddleError

logger = logging.getLogger("parwa.services.variant_addon")


# ══════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ══════════════════════════════════════════════════════════════════════════


class VariantAddonError(Exception):
    """Base exception for variant add-on operations."""

    def __init__(self, message: str, code: Optional[str] = None):
        self.code = code
        super().__init__(message)


# ══════════════════════════════════════════════════════════════════════════
# SERVICE
# ══════════════════════════════════════════════════════════════════════════


class VariantAddonService:
    """Service for managing industry variant add-ons.

    Provides methods to add, remove, list, and restore variant add-ons,
    calculate effective limits with stacking, and process period-end
    archival of removed variants.
    """

    def __init__(self, paddle_client: Optional[PaddleClient] = None):
        self._paddle_client = paddle_client

    # ── Internal helpers ────────────────────────────────────────────

    def _get_paddle_client(self) -> PaddleClient:
        """Get Paddle client (lazy init or injected)."""
        if self._paddle_client is not None:
            return self._paddle_client
        from app.clients.paddle_client import get_paddle_client

        self._paddle_client = get_paddle_client()
        return self._paddle_client

    def _get_subscription(self, db, company_id: str) -> Any:
        """Get active subscription for a company."""
        return (
            db.query(Subscription)
            .filter(
                Subscription.company_id == str(company_id),
                Subscription.status == "active",
            )
            .order_by(Subscription.created_at.desc())
            .first()
        )

    def _get_variant_config(self, variant_id: str) -> Dict[str, Any]:
        """Get add-on config for a variant_id."""
        normalized = variant_id.lower().strip()
        if normalized not in INDUSTRY_ADD_ONS:
            raise VariantAddonError(
                f"Invalid variant_id '{variant_id}'. " f"Must be one of: {
                    ', '.join(
                        sorted(
                            INDUSTRY_ADD_ONS.keys()))}",
                code="INVALID_VARIANT",
            )
        return INDUSTRY_ADD_ONS[normalized]

    def _calculate_proration_amount(
        self,
        price: Decimal,
        days_remaining: int,
        days_in_period: int,
    ) -> Decimal:
        """Calculate proration: (price / period_days) * days_remaining."""
        if days_in_period <= 0:
            return Decimal("0.00")
        daily_rate = price / Decimal(days_in_period)
        proration = daily_rate * Decimal(days_remaining)
        return proration.quantize(Decimal("0.01"))

    # ── V2: Add Variant Add-On ──────────────────────────────────────

    def add_variant(
        self,
        company_id: UUID,
        variant_id: str,
    ) -> CompanyVariantInfo:
        """Add an industry variant add-on to a company.

        Args:
            company_id: The company UUID.
            variant_id: One of ecommerce, saas, logistics, others.

        Returns:
            CompanyVariantInfo for the created add-on.

        Raises:
            VariantAddonError: If no subscription, invalid variant, or duplicate.
        """
        variant_id = variant_id.lower().strip()
        config = self._get_variant_config(variant_id)

        with SessionLocal() as db:
            # Check for active subscription
            subscription = self._get_subscription(db, str(company_id))
            if subscription is None:
                raise VariantAddonError(
                    "Company has no active subscription. "
                    "Please subscribe to a plan before adding add-ons.",
                    code="NO_SUBSCRIPTION",
                )

            # Check for duplicate
            existing = (
                db.query(CompanyVariant)
                .filter(
                    CompanyVariant.company_id == str(company_id),
                    CompanyVariant.variant_id == variant_id,
                    CompanyVariant.status.in_(["active", "inactive"]),
                )
                .first()
            )
            if existing is not None:
                raise VariantAddonError(
                    f"Variant '{variant_id}' is already active or pending removal "
                    "for this company.",
                    code="DUPLICATE_VARIANT",
                )

            # Determine price based on billing frequency
            if subscription.billing_frequency == "yearly":
                price = config["yearly_price"]
                period_days = subscription.days_in_period or 365
            else:
                price = config["price_monthly"]
                period_days = subscription.days_in_period or 30

            # Calculate proration
            now = datetime.now(timezone.utc)
            days_remaining = (
                max(0, (subscription.current_period_end - now).days)
                if subscription.current_period_end
                else period_days
            )
            proration_amount = self._calculate_proration_amount(
                price, days_remaining, period_days
            )

            # Create variant record
            variant_record = CompanyVariant(
                company_id=str(company_id),
                variant_id=variant_id,
                display_name=config["display_name"],
                status="active",
                price_per_month=config["price_monthly"],
                tickets_added=config["tickets_added"],
                kb_docs_added=config["kb_docs_added"],
                activated_at=now,
                paddle_subscription_item_id=None,
                created_at=now,
            )
            db.add(variant_record)

            # Create Paddle subscription item
            paddle_item_id = None
            try:
                paddle_client = self._get_paddle_client()
                # The paddle subscription ID is on the subscription
                paddle_result = paddle_client.update_subscription(
                    subscription.paddle_subscription_id,
                    items=[
                        {
                            "price_id": f"addon_{variant_id}_"
                            f"{subscription.billing_frequency}",
                            "quantity": 1,
                        }
                    ],
                )
                paddle_item_id = paddle_result.get("id")
                variant_record.paddle_subscription_item_id = paddle_item_id
            except PaddleError as e:
                logger.warning(
                    "variant_addon_paddle_failed company_id=%s variant=%s error=%s",
                    company_id,
                    variant_id,
                    str(e),
                )
                # Don't fail the whole operation — log and continue

            # Create proration audit
            audit = ProrationAudit(
                company_id=str(company_id),
                old_variant="none",
                new_variant=f"addon_{variant_id}",
                old_price=Decimal("0.00"),
                new_price=price,
                days_remaining=days_remaining,
                days_in_period=period_days,
                unused_amount=Decimal("0.00"),
                proration_amount=proration_amount,
                credit_applied=Decimal("0.00"),
                charge_applied=proration_amount,
                billing_cycle_start=subscription.current_period_start,
                billing_cycle_end=subscription.current_period_end,
                calculated_at=now,
            )
            db.add(audit)
            db.commit()
            db.refresh(variant_record)

            return CompanyVariantInfo.model_validate(variant_record)

    # ── V3: Remove Variant Add-On ───────────────────────────────────

    def remove_variant(
        self,
        company_id: UUID,
        variant_id: str,
    ) -> Dict[str, Any]:
        """Mark a variant add-on for removal at period end.

        Sets status to 'inactive' with deactivated_at = current period end.
        The actual archival happens in process_variant_period_end().

        Args:
            company_id: The company UUID.
            variant_id: The variant to remove.

        Returns:
            Dict with status and deactivated_at.

        Raises:
            VariantAddonError: If variant not found or already inactive.
        """
        variant_id = variant_id.lower().strip()

        with SessionLocal() as db:
            variant = (
                db.query(CompanyVariant)
                .filter(
                    CompanyVariant.company_id == str(company_id),
                    CompanyVariant.variant_id == variant_id,
                )
                .first()
            )

            if variant is None:
                raise VariantAddonError(
                    f"Variant '{variant_id}' not found for this company.",
                    code="VARIANT_NOT_FOUND",
                )

            if variant.status == "inactive":
                raise VariantAddonError(
                    f"Variant '{variant_id}' is already scheduled for removal.",
                    code="ALREADY_INACTIVE",
                )

            if variant.status == "archived":
                raise VariantAddonError(
                    f"Variant '{variant_id}' is already archived. "
                    "Use restore_variant() to re-activate.",
                    code="ALREADY_ARCHIVED",
                )

            # Get subscription for period end
            subscription = self._get_subscription(db, str(company_id))
            deactivated_at = (
                subscription.current_period_end
                if subscription and subscription.current_period_end
                else datetime.now(timezone.utc) + timedelta(days=30)
            )

            variant.status = "inactive"
            variant.deactivated_at = deactivated_at
            db.commit()

            return {
                "status": "inactive",
                "variant_id": variant_id,
                "deactivated_at": deactivated_at,
                "message": (
                    f"Variant '{variant_id}' scheduled for removal at "
                    f"{deactivated_at.isoformat()}"
                ),
            }

    # ── V4: List Variant Add-Ons ────────────────────────────────────

    def list_variants(
        self,
        company_id: UUID,
    ) -> List[CompanyVariantInfo]:
        """List all variant add-ons for a company (including inactive/archived).

        Args:
            company_id: The company UUID.

        Returns:
            List of CompanyVariantInfo objects.
        """
        with SessionLocal() as db:
            variants = (
                db.query(CompanyVariant)
                .filter(CompanyVariant.company_id == str(company_id))
                .all()
            )

            return [CompanyVariantInfo.model_validate(v) for v in variants]

    # ── V6: Effective Limits (Stacking) ────────────────────────────

    def get_effective_limits(
        self,
        company_id: UUID,
    ) -> EffectiveLimitsInfo:
        """Calculate effective limits with variant add-on stacking.

        Stacking rules:
        - tickets: base + sum(active + inactive) addon tickets
        - kb_docs: base + sum(active + inactive) addon kb_docs
        - agents/team/voice: base only (addons don't stack)
        - archived addons are EXCLUDED

        Args:
            company_id: The company UUID.

        Returns:
            EffectiveLimitsInfo with all limit calculations.
        """
        with SessionLocal() as db:
            subscription = self._get_subscription(db, str(company_id))
            tier_key = (
                subscription.tier.lower().strip() if subscription else "mini_parwa"
            )
            variant_type = VariantType(tier_key)
            base_limits = VARIANT_LIMITS[variant_type]

            # Get all active and inactive (but not archived) addons
            variants = (
                db.query(CompanyVariant)
                .filter(
                    CompanyVariant.company_id == str(company_id),
                    CompanyVariant.status.in_(["active", "inactive"]),
                )
                .all()
            )

            addon_tickets = sum(v.tickets_added for v in variants)
            addon_kb_docs = sum(v.kb_docs_added for v in variants)
            active_addon_names = [
                v.variant_id for v in variants if v.status == "active"
            ]

        effective_tickets = base_limits["monthly_tickets"] + addon_tickets
        effective_kb_docs = base_limits["kb_docs"] + addon_kb_docs
        effective_agents = base_limits["ai_agents"]
        effective_team = base_limits["team_members"]
        effective_voice = base_limits["voice_slots"]

        return EffectiveLimitsInfo(
            base_monthly_tickets=base_limits["monthly_tickets"],
            addon_tickets=addon_tickets,
            effective_monthly_tickets=effective_tickets,
            base_ai_agents=base_limits["ai_agents"],
            addon_ai_agents=0,
            effective_ai_agents=effective_agents,
            base_team_members=base_limits["team_members"],
            addon_team_members=0,
            effective_team_members=effective_team,
            base_voice_slots=base_limits["voice_slots"],
            addon_voice_slots=0,
            effective_voice_slots=effective_voice,
            base_kb_docs=base_limits["kb_docs"],
            addon_kb_docs=addon_kb_docs,
            effective_kb_docs=effective_kb_docs,
            active_addons=active_addon_names,
        )

    # ── V7: Period-End Processing ───────────────────────────────────

    def process_variant_period_end(self) -> Dict[str, Any]:
        """Process variants scheduled for removal at period end.

        Archives inactive variants whose deactivated_at has passed:
        - Sets status to 'archived'
        - Removes from Paddle subscription
        - Archives variant KB documents

        Returns:
            Dict with processing results.
        """
        now = datetime.now(timezone.utc)
        archived_count = 0
        errors: List[str] = []

        with SessionLocal() as db:
            # Find inactive variants past their deactivated_at
            variants = (
                db.query(CompanyVariant)
                .filter(
                    CompanyVariant.status == "inactive",
                    CompanyVariant.deactivated_at <= now,
                )
                .all()
            )

            for variant in variants:
                try:
                    # Archive the variant
                    variant.status = "archived"

                    # Remove from Paddle
                    if variant.paddle_subscription_item_id:
                        try:
                            paddle_client = self._get_paddle_client()
                            subscription = self._get_subscription(
                                db, variant.company_id
                            )
                            if subscription and subscription.paddle_subscription_id:
                                paddle_client.update_subscription(
                                    subscription.paddle_subscription_id,
                                    items=[
                                        {
                                            "price_id": variant.paddle_subscription_item_id,
                                            "quantity": 0,
                                        }
                                    ],
                                )
                        except PaddleError as e:
                            logger.warning(
                                "variant_archive_paddle_error variant_id=%s error=%s",
                                variant.id,
                                str(e),
                            )
                            errors.append(f"Paddle removal failed for {
                                    variant.variant_id}: {e}")

                    # V8: Archive variant-specific KB documents (tag-based)
                    try:
                        from database.models.onboarding import KnowledgeDocument

                        kb_docs = (
                            db.query(KnowledgeDocument)
                            .filter(
                                KnowledgeDocument.company_id == variant.company_id,
                                KnowledgeDocument.is_archived is False,
                            )
                            .all()
                        )
                        for doc in kb_docs:
                            # V8 Fix: Only archive variant-specific docs
                            # Check if doc has variant tag or metadata matching
                            # this variant
                            doc_tags = getattr(doc, "tags", None) or []
                            doc_metadata = getattr(doc, "metadata_json", None)
                            is_variant_doc = False

                            # Check tags for variant reference
                            if isinstance(doc_tags, list):
                                tag_str = " ".join(str(t) for t in doc_tags).lower()
                                if variant.variant_id in tag_str or "addon" in tag_str:
                                    is_variant_doc = True

                            # Check metadata for variant reference
                            if doc_metadata and isinstance(doc_metadata, str):
                                if variant.variant_id in doc_metadata.lower():
                                    is_variant_doc = True
                            elif doc_metadata and isinstance(doc_metadata, dict):
                                if doc_metadata.get("variant_id") == variant.variant_id:
                                    is_variant_doc = True

                            if is_variant_doc:
                                doc.is_archived = True
                    except Exception as e:
                        logger.warning(
                            "variant_archive_kb_error variant_id=%s error=%s",
                            variant.id,
                            str(e),
                        )
                        errors.append(
                            f"KB archival failed for {variant.variant_id}: {e}"
                        )

                    archived_count += 1

                    # V7: Send notification about variant archival
                    try:
                        from app.core.event_emitter import emit_billing_event
                        import asyncio

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                emit_billing_event(
                                    company_id=variant.company_id,
                                    event_type="variant_archived",
                                    data={
                                        "variant_id": variant.variant_id,
                                        "display_name": variant.display_name,
                                        "archived_at": now.isoformat(),
                                        "tickets_removed": variant.tickets_added,
                                        "kb_docs_removed": variant.kb_docs_added,
                                    },
                                )
                            )
                        finally:
                            loop.close()
                    except Exception as notify_err:
                        logger.warning(
                            "variant_archive_notification_failed variant_id=%s error=%s",
                            variant.id,
                            str(notify_err),
                        )

                except Exception as e:
                    errors.append(f"Error archiving {variant.variant_id}: {e}")
                    logger.error(
                        "variant_archive_error variant_id=%s error=%s",
                        variant.id,
                        str(e),
                    )

            db.commit()

        return {
            "archived_count": archived_count,
            "errors": errors,
            "processed_at": now.isoformat(),
        }

    # ── V8: Variant Restore ─────────────────────────────────────────

    def restore_variant(
        self,
        company_id: UUID,
        variant_id: str,
    ) -> Dict[str, Any]:
        """Restore an archived variant add-on.

        Re-activates the variant, un-archives KB documents,
        and creates a new Paddle subscription item.

        Args:
            company_id: The company UUID.
            variant_id: The variant to restore.

        Returns:
            Dict with status and updated info.

        Raises:
            VariantAddonError: If variant not found or not archived.
        """
        variant_id = variant_id.lower().strip()
        config = self._get_variant_config(variant_id)

        with SessionLocal() as db:
            variant = (
                db.query(CompanyVariant)
                .filter(
                    CompanyVariant.company_id == str(company_id),
                    CompanyVariant.variant_id == variant_id,
                )
                .first()
            )

            if variant is None:
                raise VariantAddonError(
                    f"Variant '{variant_id}' not found for this company.",
                    code="VARIANT_NOT_FOUND",
                )

            if variant.status != "archived":
                raise VariantAddonError(
                    f"Variant '{variant_id}' is not archived. "
                    f"Current status: {variant.status}.",
                    code="NOT_ARCHIVED",
                )

            now = datetime.now(timezone.utc)

            # Re-activate
            variant.status = "active"
            variant.activated_at = now
            variant.deactivated_at = None
            variant.display_name = config["display_name"]
            variant.price_per_month = config["price_monthly"]
            variant.tickets_added = config["tickets_added"]
            variant.kb_docs_added = config["kb_docs_added"]

            # Create new Paddle subscription item
            paddle_item_id = None
            try:
                paddle_client = self._get_paddle_client()
                subscription = self._get_subscription(db, str(company_id))
                if subscription and subscription.paddle_subscription_id:
                    paddle_result = paddle_client.update_subscription(
                        subscription.paddle_subscription_id,
                        items=[
                            {
                                "price_id": f"addon_{variant_id}_"
                                f"{subscription.billing_frequency}",
                                "quantity": 1,
                            }
                        ],
                    )
                    paddle_item_id = paddle_result.get("id")
                    variant.paddle_subscription_item_id = paddle_item_id
            except PaddleError as e:
                logger.warning(
                    "variant_restore_paddle_error company_id=%s variant=%s error=%s",
                    company_id,
                    variant_id,
                    str(e),
                )

            # Un-archive KB documents
            try:
                from database.models.onboarding import KnowledgeDocument

                kb_docs = (
                    db.query(KnowledgeDocument)
                    .filter(
                        KnowledgeDocument.company_id == str(company_id),
                        KnowledgeDocument.is_archived,
                    )
                    .all()
                )
                for doc in kb_docs:
                    doc.is_archived = False
            except Exception as e:
                logger.warning(
                    "variant_restore_kb_error company_id=%s variant=%s error=%s",
                    company_id,
                    variant_id,
                    str(e),
                )

            db.commit()

            return {
                "status": "active",
                "variant_id": variant_id,
                "display_name": config["display_name"],
                "tickets_added": config["tickets_added"],
                "kb_docs_added": config["kb_docs_added"],
                "paddle_subscription_item_id": paddle_item_id,
                "restored_at": now.isoformat(),
            }


# ══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════

_variant_addon_service: Optional[VariantAddonService] = None


def get_variant_addon_service() -> VariantAddonService:
    """Get the variant add-on service singleton."""
    global _variant_addon_service
    if _variant_addon_service is None:
        _variant_addon_service = VariantAddonService()
    return _variant_addon_service
