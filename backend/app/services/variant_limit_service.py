"""
Variant Limit Service (F-021, F-024, BC-001, BC-002, BC-007)

Handles subscription variant limit enforcement:
- Get variant limits (starter / growth / high)
- Check ticket, team member, AI agent, voice slot, and KB doc limits
- Enforce limits by blocking operations when exceeded
- Provide current usage counts against plan limits

Locked Variant Limits:
  | Variant | Tickets | AI Agents | Team | Voice | KB Docs | Price    |
  |---------|---------|-----------|------|-------|---------|----------|
  | Starter | 2,000   | 1         | 3    | 0     | 100     | $999.00  |
  | Growth  | 5,000   | 3         | 10   | 2     | 500     | $2,499.00|
  | High    | 15,000  | 5         | 25   | 5     | 2,000   | $3,999.00|

BC-001: All methods validate company_id
BC-002: All money calculations use Decimal
BC-007: Feature gating per variant tier
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing_extended import VariantLimit, get_variant_limits
from database.models.billing import Subscription
from database.models.core import Company

logger = logging.getLogger("parwa.services.variant_limit")

# ── Constants ──────────────────────────────────────────────────────────────

VALID_LIMIT_TYPES = {"tickets", "team_members", "ai_agents", "voice_slots", "kb_docs"}

_LIMIT_KEY_MAP = {
    "tickets": "monthly_tickets",
    "team_members": "team_members",
    "ai_agents": "ai_agents",
    "voice_slots": "voice_slots",
    "kb_docs": "kb_docs",
}

_LIMIT_LABEL_MAP = {
    "tickets": "monthly tickets",
    "team_members": "team members",
    "ai_agents": "AI agents",
    "voice_slots": "voice slots",
    "kb_docs": "knowledge base documents",
}

_HARDCODED_LIMITS: Dict[str, Dict[str, Any]] = {
    "starter": {
        "monthly_tickets": 2000, "ai_agents": 1, "team_members": 3,
        "voice_slots": 0, "kb_docs": 100, "price": "999.00",
    },
    "growth": {
        "monthly_tickets": 5000, "ai_agents": 3, "team_members": 10,
        "voice_slots": 2, "kb_docs": 500, "price": "2499.00",
    },
    "high": {
        "monthly_tickets": 15000, "ai_agents": 5, "team_members": 25,
        "voice_slots": 5, "kb_docs": 2000, "price": "3999.00",
    },
}


# ══════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ══════════════════════════════════════════════════════════════════════════


class VariantLimitError(Exception):
    """Base exception for variant limit errors."""

    def __init__(
        self,
        message: str,
        limit_type: Optional[str] = None,
        current_usage: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> None:
        self.limit_type = limit_type
        self.current_usage = current_usage
        self.limit = limit
        super().__init__(message)


class VariantLimitExceededError(VariantLimitError):
    """Raised when a variant limit is exceeded.

    Attributes:
        limit_type: Resource type (tickets, team_members, etc.).
        current_usage: Current usage count.
        limit: Plan limit for this resource.
        message: Human-readable description with upgrade guidance.
    """

    def __init__(
        self,
        limit_type: str,
        current_usage: int,
        limit: int,
        message: Optional[str] = None,
    ) -> None:
        label = _LIMIT_LABEL_MAP.get(limit_type, limit_type)
        if message is None:
            message = (
                f"{label.title()} limit exceeded: "
                f"{current_usage}/{limit} used. "
                f"Please upgrade your plan to increase this limit."
            )
        super().__init__(
            message=message,
            limit_type=limit_type,
            current_usage=current_usage,
            limit=limit,
        )


# ══════════════════════════════════════════════════════════════════════════
# SERVICE
# ══════════════════════════════════════════════════════════════════════════


class VariantLimitService:
    """Variant Limit enforcement service.

    Provides methods to query plan limits, check current usage against
    those limits, and enforce hard caps that block prohibited operations.

    Usage::

        service = get_variant_limit_service()

        # Check a single limit
        result = service.check_ticket_limit(company_id=uuid, current_count=1500)
        if not result["allowed"]:
            raise VariantLimitExceededError(...)

        # Generic enforcement — raises on violation
        service.enforce_limit(company_id=uuid, limit_type="ai_agents")

        # Full limit dashboard
        all_checks = service.get_all_limit_checks(company_id=uuid)
    """

    # ── Validation Helpers ──────────────────────────────────────────

    @staticmethod
    def _validate_company_id(company_id: Any) -> str:
        """Validate and normalise company_id (BC-001)."""
        if company_id is None:
            raise VariantLimitError("company_id is required")
        cid = str(company_id).strip()
        if not cid:
            raise VariantLimitError("company_id cannot be empty")
        return cid

    @staticmethod
    def _validate_limit_type(limit_type: str) -> str:
        """Validate limit_type is a recognised key."""
        lt = limit_type.lower().strip()
        if lt not in VALID_LIMIT_TYPES:
            raise VariantLimitError(
                f"Invalid limit_type '{limit_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_LIMIT_TYPES))}"
            )
        return lt

    def _get_company_variant(self, db: Session, company_id: str) -> str:
        """Look up the subscription tier for a company.

        Falls back to ``"starter"`` when the company has no active
        subscription (new / trial accounts).
        """
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.company_id == company_id,
                Subscription.status == "active",
            )
            .order_by(Subscription.created_at.desc())
            .first()
        )
        if subscription and subscription.tier:
            return subscription.tier.lower().strip()

        # Also check Company.subscription_tier field
        company = db.query(Company).filter(Company.id == company_id).first()
        if company and getattr(company, "subscription_tier", None):
            return company.subscription_tier.lower().strip()

        logger.info(
            "variant_limit_default_starter company_id=%s reason=no_subscription",
            company_id,
        )
        return "starter"

    # ── Public API ──────────────────────────────────────────────────

    def get_variant_limits(self, variant: str) -> Dict[str, Any]:
        """Get limits for a specific variant.

        Primary source: ``get_variant_limits()`` from billing_extended.
        Fallback: direct query of the ``VariantLimit`` DB table, then
        hardcoded defaults.
        """
        variant_key = variant.lower().strip()

        # Primary — billing_extended helper
        limits = get_variant_limits(variant_key)
        if limits:
            logger.info(
                "variant_limits_loaded variant=%s source=billing_extended",
                variant_key,
            )
            return limits

        # Fallback — VariantLimit DB table
        with SessionLocal() as db:
            row = (
                db.query(VariantLimit)
                .filter(VariantLimit.variant_name == variant_key)
                .first()
            )
            if row:
                limits = {
                    "monthly_tickets": row.monthly_tickets,
                    "ai_agents": row.ai_agents,
                    "team_members": row.team_members,
                    "voice_slots": row.voice_slots,
                    "kb_docs": row.kb_docs,
                    "price": str(row.price) if row.price else "0",
                }
                logger.info(
                    "variant_limits_loaded variant=%s source=db_table",
                    variant_key,
                )
                return limits

        # Final fallback — hardcoded
        logger.warning(
            "variant_limits_fallback variant=%s source=hardcoded",
            variant_key,
        )
        return dict(_HARDCODED_LIMITS.get(variant_key, _HARDCODED_LIMITS["starter"]))

    def get_company_limits(self, company_id: Any) -> Dict[str, Any]:
        """Get effective limits for a company based on their subscription tier."""
        company_id_str = self._validate_company_id(company_id)

        with SessionLocal() as db:
            variant = self._get_company_variant(db, company_id_str)
            limits = self.get_variant_limits(variant)

        logger.info(
            "company_limits_retrieved company_id=%s variant=%s",
            company_id_str,
            variant,
        )
        return {"company_id": company_id_str, "variant": variant, **limits}

    def _get_addon_tickets(self, company_id: str, db: Session) -> int:
        """V6: Get stacked addon ticket allocations for a company.

        Queries active and inactive (but not archived) CompanyVariant
        records and sums their tickets_added. This is added to the base
        plan ticket limit for effective enforcement.
        """
        from database.models.billing_extended import CompanyVariant

        try:
            addons = (
                db.query(func.sum(CompanyVariant.tickets_added))
                .filter(
                    CompanyVariant.company_id == company_id,
                    CompanyVariant.status.in_(["active", "inactive"]),
                )
                .scalar()
            )
            return int(addons) if addons else 0
        except Exception as exc:
            logger.warning(
                "addon_tickets_query_failed company_id=%s error=%s",
                company_id, str(exc),
            )
            return 0

    def _get_addon_kb_docs(self, company_id: str, db: Session) -> int:
        """V6: Get stacked addon KB doc allocations for a company.

        Queries active and inactive (but not archived) CompanyVariant
        records and sums their kb_docs_added. This is added to the base
        plan KB doc limit for effective enforcement.
        """
        from database.models.billing_extended import CompanyVariant

        try:
            addons = (
                db.query(func.sum(CompanyVariant.kb_docs_added))
                .filter(
                    CompanyVariant.company_id == company_id,
                    CompanyVariant.status.in_(["active", "inactive"]),
                )
                .scalar()
            )
            return int(addons) if addons else 0
        except Exception as exc:
            logger.warning(
                "addon_kb_docs_query_failed company_id=%s error=%s",
                company_id, str(exc),
            )
            return 0

    def check_ticket_limit(
        self,
        company_id: Any,
        current_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Check if a company can create more tickets this month.

        V6: Includes variant addon ticket stacking.
        effective_ticket_limit = base_plan_tickets + sum(addon tickets)

        If ``current_count`` is ``None``, queries ``UsageRecord`` to
        sum tickets_used for the current month.

        Returns:
            Dict with allowed, current_usage, limit, remaining, message.
        """
        company_id_str = self._validate_company_id(company_id)

        with SessionLocal() as db:
            variant = self._get_company_variant(db, company_id_str)
            limits = self.get_variant_limits(variant)
            base_ticket_limit = limits.get("monthly_tickets", 2000)

            # V6: Stack addon tickets
            addon_tickets = self._get_addon_tickets(company_id_str, db)
            ticket_limit = base_ticket_limit + addon_tickets

            if current_count is not None:
                usage = int(current_count)
            else:
                from database.models.billing_extended import UsageRecord

                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                total = (
                    db.query(func.sum(UsageRecord.tickets_used))
                    .filter(
                        UsageRecord.company_id == company_id_str,
                        UsageRecord.record_month == current_month,
                    )
                    .scalar()
                ) or 0
                usage = int(total)

        remaining = max(0, ticket_limit - usage)
        allowed = usage < ticket_limit

        result = {
            "limit_type": "tickets",
            "allowed": allowed,
            "current_usage": usage,
            "limit": ticket_limit,
            "remaining": remaining,
            "variant": variant,
            "addon_tickets": addon_tickets,
            "base_limit": base_ticket_limit,
            "message": (
                f"{usage}/{ticket_limit} tickets used this month "
                f"(base: {base_ticket_limit} + addons: {addon_tickets}). "
                f"{remaining} remaining."
            )
            if allowed
            else (
                f"Ticket limit exceeded: {usage}/{ticket_limit}. "
                f"Upgrade your plan or remove add-ons to adjust capacity."
            ),
        }

        logger.info(
            "ticket_limit_checked company_id=%s variant=%s "
            "usage=%s limit=%s addon_tickets=%s allowed=%s",
            company_id_str, variant, usage, ticket_limit, addon_tickets, allowed,
        )
        return result

    def check_team_member_limit(
        self, company_id: Any, current_count: int
    ) -> Dict[str, Any]:
        """Check if a company can add more team members."""
        return self._check_count_limit(company_id, "team_members", current_count)

    def check_ai_agent_limit(
        self, company_id: Any, current_count: int
    ) -> Dict[str, Any]:
        """Check if a company can create more AI agents."""
        return self._check_count_limit(company_id, "ai_agents", current_count)

    def check_voice_slot_limit(
        self, company_id: Any, current_count: int
    ) -> Dict[str, Any]:
        """Check if a company can provision more voice slots."""
        return self._check_count_limit(company_id, "voice_slots", current_count)

    def check_kb_doc_limit(
        self, company_id: Any, current_count: int
    ) -> Dict[str, Any]:
        """Check if a company can upload more KB documents."""
        return self._check_count_limit(company_id, "kb_docs", current_count)

    def enforce_limit(
        self,
        company_id: Any,
        limit_type: str,
        current_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Enforce a variant limit. Raises :class:`VariantLimitExceededError`
        when the limit has been reached or exceeded.

        For ``limit_type="tickets"`` with ``current_count=None``, the
        service automatically queries ``UsageRecord`` for the current month.
        For all other types, ``current_count`` is required.

        Returns:
            Dict with limit check details when within limits.

        Raises:
            VariantLimitExceededError: When usage >= plan limit.
        """
        lt = self._validate_limit_type(limit_type)

        if lt == "tickets":
            check_result = self.check_ticket_limit(
                company_id, current_count=current_count
            )
        else:
            if current_count is None:
                raise VariantLimitError(
                    f"current_count is required for limit_type '{lt}'"
                )
            check_result = self._check_count_limit(
                company_id, lt, int(current_count)
            )

        if not check_result["allowed"]:
            logger.warning(
                "variant_limit_exceeded company_id=%s limit_type=%s "
                "usage=%s limit=%s",
                check_result.get("company_id", company_id),
                lt,
                check_result["current_usage"],
                check_result["limit"],
            )
            raise VariantLimitExceededError(
                limit_type=lt,
                current_usage=check_result["current_usage"],
                limit=check_result["limit"],
                message=check_result["message"],
            )

        return check_result

    def get_all_limit_checks(self, company_id: Any) -> Dict[str, Any]:
        """Run all five limit checks for a company in a single call.

        V6: Tickets and KB docs include addon stacking.
        Agents, team, voice do NOT stack.

        Tickets usage is computed from ``UsageRecord`` for the current
        month. Other counts are queried from their respective tables.

        Returns:
            Dict with company_id, variant, and one sub-dict per limit_type.
        """
        company_id_str = self._validate_company_id(company_id)

        with SessionLocal() as db:
            variant = self._get_company_variant(db, company_id_str)
            limits = self.get_variant_limits(variant)

            # V6: Get addon allocations for stacking
            addon_tickets = self._get_addon_tickets(company_id_str, db)
            addon_kb_docs = self._get_addon_kb_docs(company_id_str, db)

        ticket_check = self.check_ticket_limit(company_id_str)
        team_count = self._query_resource_count(company_id_str, "team_members")
        ai_count = self._query_resource_count(company_id_str, "ai_agents")
        voice_count = self._query_resource_count(company_id_str, "voice_slots")
        kb_count = self._query_resource_count(company_id_str, "kb_docs")

        base_kb_limit = limits.get("kb_docs", 100)
        effective_kb_limit = base_kb_limit + addon_kb_docs

        checks: Dict[str, Dict[str, Any]] = {
            "tickets": ticket_check,
            "team_members": self._build_check_result(
                "team_members", team_count, limits.get("team_members", 3)
            ),
            "ai_agents": self._build_check_result(
                "ai_agents", ai_count, limits.get("ai_agents", 1)
            ),
            "voice_slots": self._build_check_result(
                "voice_slots", voice_count, limits.get("voice_slots", 0)
            ),
            "kb_docs": self._build_check_result(
                "kb_docs", kb_count, effective_kb_limit
            ),
        }

        logger.info(
            "all_limit_checks company_id=%s variant=%s "
            "tickets=%s/%s team=%s/%s agents=%s/%s "
            "voice=%s/%s kb=%s/%s",
            company_id_str, variant,
            checks["tickets"]["current_usage"], checks["tickets"]["limit"],
            checks["team_members"]["current_usage"], checks["team_members"]["limit"],
            checks["ai_agents"]["current_usage"], checks["ai_agents"]["limit"],
            checks["voice_slots"]["current_usage"], checks["voice_slots"]["limit"],
            checks["kb_docs"]["current_usage"], checks["kb_docs"]["limit"],
        )

        return {"company_id": company_id_str, "variant": variant, "checks": checks}

    # ── Private Helpers ─────────────────────────────────────────────

    def _check_count_limit(
        self, company_id: Any, limit_type: str, current_count: int,
    ) -> Dict[str, Any]:
        """Generic count-based limit check for non-ticket resources.

        V6: For kb_docs, includes addon KB doc stacking.
        Agents, team, voice do NOT stack with addons.
        """
        company_id_str = self._validate_company_id(company_id)
        lt = self._validate_limit_type(limit_type)

        with SessionLocal() as db:
            variant = self._get_company_variant(db, company_id_str)
            limits = self.get_variant_limits(variant)

            base_limit = limits.get(_LIMIT_KEY_MAP[lt], 0)

            # V6: KB docs stack with addon allocations
            addon_amount = 0
            if lt == "kb_docs":
                addon_amount = self._get_addon_kb_docs(company_id_str, db)

            plan_limit = base_limit + addon_amount

        usage = int(current_count)
        remaining = max(0, plan_limit - usage)
        allowed = usage < plan_limit
        label = _LIMIT_LABEL_MAP[lt]

        result = {
            "limit_type": lt,
            "allowed": allowed,
            "current_usage": usage,
            "limit": plan_limit,
            "remaining": remaining,
            "variant": variant,
            "base_limit": base_limit,
            "addon_amount": addon_amount,
            "message": (
                f"{usage}/{plan_limit} {label} in use. {remaining} remaining."
                + (f" (base: {base_limit} + addons: {addon_amount})" if addon_amount else "")
            ) if allowed else (
                f"{label.title()} limit exceeded: {usage}/{plan_limit}. "
                f"Upgrade your plan to add more {label}."
            ),
        }

        logger.info(
            "count_limit_checked company_id=%s variant=%s "
            "limit_type=%s usage=%s limit=%s base=%s addon=%s allowed=%s",
            company_id_str, variant, lt, usage, plan_limit, base_limit, addon_amount, allowed,
        )
        return result

    @staticmethod
    def _build_check_result(
        limit_type: str, current_count: int, limit: int,
    ) -> Dict[str, Any]:
        """Build a standard check result dict without DB access."""
        usage = int(current_count)
        remaining = max(0, limit - usage)
        allowed = usage < limit
        label = _LIMIT_LABEL_MAP.get(limit_type, limit_type)

        return {
            "limit_type": limit_type,
            "allowed": allowed,
            "current_usage": usage,
            "limit": limit,
            "remaining": remaining,
            "message": (
                f"{usage}/{limit} {label} in use. {remaining} remaining."
            ) if allowed else (
                f"{label.title()} limit exceeded: {usage}/{limit}. "
                f"Upgrade your plan to add more {label}."
            ),
        }

    def _query_resource_count(self, company_id: str, limit_type: str) -> int:
        """Query the current count for a non-ticket resource type.

        Maps limit_type to its model:
          team_members → CompanyUser
          ai_agents → AIAgent
          voice_slots → VoiceSlot
          kb_docs → KBDocument

        Returns 0 on any error (BC-008 graceful degradation).
        """
        _MODEL_MAP = {
            "team_members": ("database.models.core", "CompanyUser"),
            "ai_agents": ("database.models.agent", "AIAgent"),
            "voice_slots": ("database.models.voice", "VoiceSlot"),
            "kb_docs": ("database.models.knowledge_base", "KBDocument"),
        }
        entry = _MODEL_MAP.get(limit_type)
        if entry is None:
            return 0

        try:
            module_path, model_name = entry
            import importlib
            module = importlib.import_module(module_path)
            model_cls = getattr(module, model_name)

            with SessionLocal() as db:
                count = (
                    db.query(func.count(model_cls.id))
                    .filter(model_cls.company_id == company_id)
                    .scalar()
                )
                return int(count or 0)
        except Exception as exc:
            logger.warning(
                "resource_count_query_failed company_id=%s "
                "limit_type=%s error=%s",
                company_id, limit_type, str(exc),
            )
            return 0


# ══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════

_variant_limit_service: Optional[VariantLimitService] = None


def get_variant_limit_service() -> VariantLimitService:
    """Get the variant limit service singleton.

    Creates the instance on first call and reuses it for all
    subsequent calls (module-level caching).
    """
    global _variant_limit_service
    if _variant_limit_service is None:
        _variant_limit_service = VariantLimitService()
    return _variant_limit_service
