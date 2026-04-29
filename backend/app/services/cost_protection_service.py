"""
AI Engine Cost Overrun Protection (SG-35).

Track per-tenant daily/monthly token usage.
Hard-stop at budget limit. Alert at 80%.
Per-variant default limits:
  Mini PARWA:   500,000 tokens/day,   15,000,000 tokens/month
  PARWA:       2,000,000 tokens/day,  60,000,000 tokens/month
  PARWA High:  5,000,000 tokens/day, 150,000,000 tokens/month

BC-001: company_id is second parameter.
BC-002: Token counts use Integer (no Float for counting).
BC-007: All AI through Smart Router.
BC-008: Graceful degradation.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.exceptions import ParwaBaseError

from database.models.variant_engine import AITokenBudget

logger = logging.getLogger("parwa.cost_protection")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class BudgetPeriodType(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"


class BudgetStatus(str, Enum):
    ACTIVE = "active"
    EXCEEDED = "exceeded"
    DISABLED = "disabled"
    EXHAUSTED = "exhausted"


class AlertLevel(str, Enum):
    NONE = "none"
    WARNING = "warning"  # >= 80%
    CRITICAL = "critical"  # >= 95%
    EXHAUSTED = "exhausted"  # >= 100%


# ══════════════════════════════════════════════════════════════════
# DEFAULTS
# ══════════════════════════════════════════════════════════════════

DEFAULT_VARIANT_LIMITS = {
    "mini_parwa": {"daily": 500_000, "monthly": 15_000_000},
    "parwa": {"daily": 2_000_000, "monthly": 60_000_000},
    "high_parwa": {"daily": 5_000_000, "monthly": 150_000_000},
}

# Per-tier daily request limits to protect MEDIUM bottleneck
# MEDIUM bottleneck: 2,500 req/day across all providers
TIER_DAILY_REQUEST_LIMITS = {
    "light": 100_000,  # Light has plenty of headroom
    "medium": 2_500,  # MEDIUM bottleneck — strict limit
    "heavy": 500,  # HEAVY is expensive — conservative
    "guardrail": 50_000,  # Guardrail checks are cheap
}

VALID_VARIANT_TYPES = set(DEFAULT_VARIANT_LIMITS.keys())
VALID_BUDGET_TYPES = {BudgetPeriodType.DAILY.value, BudgetPeriodType.MONTHLY.value}


# ══════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class TokenUsageRecord:
    company_id: str
    instance_id: Optional[str] = None
    model_id: str = ""
    provider: str = ""
    tier: str = ""
    tokens_used: int = 0
    atomic_step_type: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    budget_period: str = ""
    budget_type: str = ""


@dataclass
class BudgetCheckResult:
    allowed: bool = False
    remaining_tokens: int = 0
    usage_pct: float = 0.0
    alert_level: AlertLevel = AlertLevel.NONE
    budget_status: BudgetStatus = BudgetStatus.ACTIVE
    reason: str = ""


# ══════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════


def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required."""
    if not company_id or not str(company_id).strip():
        raise ParwaBaseError(
            error_code="INVALID_COMPANY_ID",
            message="company_id is required and cannot be empty",
            status_code=400,
        )


def _validate_tokens_non_negative(tokens: int) -> None:
    """BC-002: Token counts must be non-negative integers."""
    if not isinstance(tokens, int) or tokens < 0:
        raise ParwaBaseError(
            error_code="INVALID_TOKEN_COUNT",
            message="tokens_used must be a non-negative integer",
            status_code=400,
        )


def _validate_budget_type(budget_type: str) -> None:
    """Validate budget_type is daily or monthly."""
    if budget_type not in VALID_BUDGET_TYPES:
        raise ParwaBaseError(
            error_code="INVALID_BUDGET_TYPE",
            message=f"budget_type must be one of: {VALID_BUDGET_TYPES}",
            status_code=400,
        )


def _validate_variant_type(variant_type: str) -> None:
    """Validate variant_type is a known type."""
    if variant_type not in VALID_VARIANT_TYPES:
        raise ParwaBaseError(
            error_code="INVALID_VARIANT_TYPE",
            message=(
                f"Invalid variant_type '{variant_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_VARIANT_TYPES))}"
            ),
            status_code=400,
        )


# ══════════════════════════════════════════════════════════════════
# COST PROTECTION SERVICE
# ══════════════════════════════════════════════════════════════════


class CostProtectionService:
    """
    AI Engine Cost Overrun Protection Service.

    Track per-tenant daily/monthly token usage.
    Hard-stop at budget limit. Alert at 80%.

    All public methods are wrapped in try/except for BC-008.
    """

    def __init__(self, db) -> None:
        self.db = db

    # ── Budget Initialization ────────────────────────────────────

    def initialize_budgets(
        self,
        company_id: str,
        variant_type: str,
        instance_id: Optional[str] = None,
    ) -> dict:
        """
        Create daily + monthly budget records for a tenant/instance
        using DEFAULT_VARIANT_LIMITS. Idempotent — skip if exists
        for current period.
        """
        try:
            _validate_company_id(company_id)
            _validate_variant_type(variant_type)

            limits = self._get_variant_limits(variant_type)
            created = []

            for budget_type in ("daily", "monthly"):
                period = self._get_current_period(budget_type)
                max_tokens = limits[budget_type]

                budget = self._get_or_create_budget(
                    company_id=company_id,
                    budget_type=budget_type,
                    budget_period=period,
                    instance_id=instance_id,
                    max_tokens=max_tokens,
                )

                created.append(
                    {
                        "budget_type": budget_type,
                        "budget_period": period,
                        "max_tokens": budget.max_tokens,
                        "status": budget.status,
                        "id": budget.id,
                    }
                )

            logger.info(
                "budgets_initialized",
                extra={
                    "company_id": company_id,
                    "variant_type": variant_type,
                    "instance_id": instance_id,
                    "budgets_created": len(created),
                },
            )

            return {
                "company_id": company_id,
                "variant_type": variant_type,
                "instance_id": instance_id,
                "budgets": created,
            }
        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "budget_init_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            # BC-008: Graceful degradation — return empty, don't crash
            return {
                "company_id": company_id,
                "variant_type": variant_type,
                "instance_id": instance_id,
                "budgets": [],
                "error": str(exc),
            }

    # ── Budget Checking ──────────────────────────────────────────

    def check_budget(
        self,
        company_id: str,
        requested_tokens: int,
        budget_type: str = "daily",
        instance_id: Optional[str] = None,
    ) -> BudgetCheckResult:
        """
        Check if request is within budget.
        Returns BudgetCheckResult with allowed=True/False.
        """
        try:
            _validate_company_id(company_id)
            _validate_budget_type(budget_type)

            # Zero tokens always allowed
            if requested_tokens == 0:
                return BudgetCheckResult(
                    allowed=True,
                    remaining_tokens=0,
                    usage_pct=0.0,
                    alert_level=AlertLevel.NONE,
                    budget_status=BudgetStatus.ACTIVE,
                    reason="Zero token request — always allowed",
                )

            _validate_tokens_non_negative(requested_tokens)

            period = self._get_current_period(budget_type)
            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type=budget_type,
                    budget_period=period,
                    instance_id=instance_id,
                )
                .first()
            )

            # No budget record found — allow but warn (BC-008)
            if budget is None:
                logger.warning(
                    "no_budget_found_allowing",
                    extra={
                        "company_id": company_id,
                        "budget_type": budget_type,
                        "period": period,
                    },
                )
                return BudgetCheckResult(
                    allowed=True,
                    remaining_tokens=requested_tokens,
                    usage_pct=0.0,
                    alert_level=AlertLevel.NONE,
                    budget_status=BudgetStatus.ACTIVE,
                    reason="No budget record found — request allowed (graceful degradation)",
                )

            # Disabled budget — always allow
            if budget.status == "disabled":
                return BudgetCheckResult(
                    allowed=True,
                    remaining_tokens=budget.max_tokens - budget.used_tokens,
                    usage_pct=self._calc_usage_pct(
                        budget.used_tokens, budget.max_tokens
                    ),
                    alert_level=AlertLevel.NONE,
                    budget_status=BudgetStatus.DISABLED,
                    reason="Budget disabled — request allowed",
                )

            remaining = budget.max_tokens - budget.used_tokens
            usage_pct = self._calc_usage_pct(budget.used_tokens, budget.max_tokens)
            alert_level = self._check_alert(budget)

            # Request exceeds remaining tokens
            if requested_tokens > remaining:
                return BudgetCheckResult(
                    allowed=False,
                    remaining_tokens=remaining,
                    usage_pct=usage_pct,
                    alert_level=alert_level,
                    budget_status=budget.status,
                    reason=f"Requested {requested_tokens} tokens exceeds remaining {remaining}",
                )

            # Check if this request would push to/exceed limit AND hard_stop is
            # on
            new_used = budget.used_tokens + requested_tokens
            if new_used >= budget.max_tokens and budget.hard_stop:
                # Only block if this specific request pushes OVER the limit
                if new_used > budget.max_tokens:
                    return BudgetCheckResult(
                        allowed=False,
                        remaining_tokens=budget.max_tokens - budget.used_tokens,
                        usage_pct=usage_pct,
                        alert_level=alert_level,
                        budget_status=BudgetStatus.EXHAUSTED,
                        reason="Hard stop enabled — request would exceed budget",
                    )

            return BudgetCheckResult(
                allowed=True,
                remaining_tokens=remaining - requested_tokens,
                usage_pct=usage_pct,
                alert_level=alert_level,
                budget_status=BudgetStatus.ACTIVE,
                reason="Within budget",
            )

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "budget_check_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            # BC-008: Allow on error
            return BudgetCheckResult(
                allowed=True,
                remaining_tokens=0,
                usage_pct=0.0,
                alert_level=AlertLevel.NONE,
                budget_status=BudgetStatus.ACTIVE,
                reason=f"Budget check error — request allowed (graceful degradation): {
                    str(exc)}",
            )

    # ── Usage Recording ──────────────────────────────────────────

    def record_usage(
        self,
        company_id: str,
        tokens_used: int,
        model_id: str = "",
        provider: str = "",
        tier: str = "",
        atomic_step: str = "",
        instance_id: Optional[str] = None,
    ) -> dict:
        """
        Record token usage. Updates both daily and monthly budgets.
        Returns updated usage stats.
        """
        try:
            _validate_company_id(company_id)
            _validate_tokens_non_negative(tokens_used)

            if tokens_used == 0:
                return {
                    "company_id": company_id,
                    "tokens_recorded": 0,
                    "daily": {"used_tokens": 0},
                    "monthly": {"used_tokens": 0},
                    "reason": "Zero tokens — nothing to record",
                }

            updated = {}

            for budget_type in ("daily", "monthly"):
                period = self._get_current_period(budget_type)

                budget = (
                    self.db.query(AITokenBudget)
                    .filter_by(
                        company_id=company_id,
                        budget_type=budget_type,
                        budget_period=period,
                        instance_id=instance_id,
                    )
                    .first()
                )

                if budget is None:
                    logger.warning(
                        "no_budget_for_recording",
                        extra={
                            "company_id": company_id,
                            "budget_type": budget_type,
                            "period": period,
                        },
                    )
                    updated[budget_type] = {
                        "used_tokens": 0,
                        "max_tokens": 0,
                        "status": "no_budget",
                    }
                    continue

                if budget.status == "disabled":
                    updated[budget_type] = {
                        "used_tokens": budget.used_tokens,
                        "max_tokens": budget.max_tokens,
                        "status": budget.status,
                    }
                    continue

                budget.used_tokens = (budget.used_tokens or 0) + tokens_used
                budget.updated_at = datetime.now(timezone.utc)

                # Check if budget is now exceeded
                if budget.used_tokens >= budget.max_tokens:
                    budget.status = "exceeded"

                # Check alert thresholds
                alert = self._check_alert(budget)
                if alert != AlertLevel.NONE and not budget.alert_sent:
                    budget.alert_sent = True
                    logger.warning(
                        "budget_alert_triggered",
                        extra={
                            "company_id": company_id,
                            "budget_type": budget_type,
                            "period": period,
                            "alert_level": alert.value,
                            "usage_pct": self._calc_usage_pct(
                                budget.used_tokens,
                                budget.max_tokens,
                            ),
                        },
                    )

                updated[budget_type] = {
                    "used_tokens": budget.used_tokens,
                    "max_tokens": budget.max_tokens,
                    "status": budget.status,
                    "alert_level": alert.value,
                }

            self.db.commit()

            logger.info(
                "token_usage_recorded",
                extra={
                    "company_id": company_id,
                    "tokens_used": tokens_used,
                    "model_id": model_id,
                    "provider": provider,
                },
            )

            return {
                "company_id": company_id,
                "tokens_recorded": tokens_used,
                "daily": updated.get("daily", {}),
                "monthly": updated.get("monthly", {}),
            }

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "record_usage_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return {
                "company_id": company_id,
                "tokens_recorded": tokens_used,
                "daily": {"used_tokens": 0, "error": str(exc)},
                "monthly": {"used_tokens": 0, "error": str(exc)},
                "reason": "Recording failed (graceful degradation)",
            }

    # ── Usage Retrieval ──────────────────────────────────────────

    def get_usage(
        self,
        company_id: str,
        budget_type: str = "daily",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Get current usage stats for a budget type."""
        try:
            _validate_company_id(company_id)
            _validate_budget_type(budget_type)

            period = self._get_current_period(budget_type)
            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type=budget_type,
                    budget_period=period,
                    instance_id=instance_id,
                )
                .first()
            )

            if budget is None:
                return {
                    "company_id": company_id,
                    "budget_type": budget_type,
                    "period": period,
                    "found": False,
                }

            usage_pct = self._calc_usage_pct(budget.used_tokens, budget.max_tokens)
            alert_level = self._check_alert(budget)

            return {
                "company_id": company_id,
                "budget_type": budget_type,
                "period": period,
                "found": True,
                "used_tokens": budget.used_tokens or 0,
                "max_tokens": budget.max_tokens,
                "remaining_tokens": max(
                    0, budget.max_tokens - (budget.used_tokens or 0)
                ),
                "usage_pct": usage_pct,
                "alert_level": alert_level.value,
                "status": budget.status,
                "hard_stop": budget.hard_stop,
                "alert_sent": budget.alert_sent,
                "instance_id": budget.instance_id,
            }

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("get_usage_failed", extra={"error": str(exc)})
            return {"error": str(exc)}

    # ── Monthly Report ───────────────────────────────────────────

    def get_monthly_report(self, company_id: str) -> dict:
        """Full monthly breakdown by day."""
        try:
            _validate_company_id(company_id)

            period = self._get_current_period("monthly")
            budgets = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type="daily",
                )
                .all()
            )

            daily_breakdown = []
            total_used = 0

            for b in budgets:
                daily_breakdown.append(
                    {
                        "period": b.budget_period,
                        "used_tokens": b.used_tokens or 0,
                        "max_tokens": b.max_tokens,
                        "status": b.status,
                        "instance_id": b.instance_id,
                    }
                )
                total_used += b.used_tokens or 0

            monthly_budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type="monthly",
                    budget_period=period,
                )
                .first()
            )

            return {
                "company_id": company_id,
                "month": period,
                "monthly_budget": (
                    {
                        "used_tokens": (
                            monthly_budget.used_tokens if monthly_budget else 0
                        ),
                        "max_tokens": (
                            monthly_budget.max_tokens if monthly_budget else 0
                        ),
                        "status": (
                            monthly_budget.status if monthly_budget else "no_budget"
                        ),
                    }
                    if monthly_budget
                    else {"status": "no_budget"}
                ),
                "daily_breakdown": daily_breakdown,
                "total_daily_tokens": total_used,
            }

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("monthly_report_failed", extra={"error": str(exc)})
            return {"error": str(exc)}

    # ── Reset Daily Budgets ──────────────────────────────────────

    def reset_daily_budgets(self, company_id: str) -> dict:
        """Reset all daily budgets for a tenant. Call at midnight."""
        try:
            _validate_company_id(company_id)

            budgets = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type="daily",
                )
                .all()
            )

            reset_count = 0
            for budget in budgets:
                budget.used_tokens = 0
                budget.status = "active"
                budget.alert_sent = False
                budget.updated_at = datetime.now(timezone.utc)
                reset_count += 1

            self.db.commit()

            logger.info(
                "daily_budgets_reset",
                extra={"company_id": company_id, "reset_count": reset_count},
            )

            return {
                "company_id": company_id,
                "budgets_reset": reset_count,
                "message": f"Reset {reset_count} daily budgets for company {company_id}",
            }

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("reset_failed", extra={"error": str(exc)})
            return {"error": str(exc), "budgets_reset": 0}

    # ── Admin: Update Limit ──────────────────────────────────────

    def update_budget_limit(
        self,
        company_id: str,
        budget_type: str,
        new_max_tokens: int,
        instance_id: Optional[str] = None,
    ) -> Optional[AITokenBudget]:
        """Admin: change the max_tokens limit."""
        try:
            _validate_company_id(company_id)
            _validate_budget_type(budget_type)
            _validate_tokens_non_negative(new_max_tokens)

            if new_max_tokens == 0:
                raise ParwaBaseError(
                    error_code="INVALID_BUDGET_LIMIT",
                    message="max_tokens must be greater than zero",
                    status_code=400,
                )

            period = self._get_current_period(budget_type)
            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type=budget_type,
                    budget_period=period,
                    instance_id=instance_id,
                )
                .first()
            )

            if budget is None:
                raise ParwaBaseError(
                    error_code="BUDGET_NOT_FOUND",
                    message=(
                        f"No {budget_type} budget found for company "
                        f"'{company_id}' in period '{period}'"
                    ),
                    status_code=404,
                )

            old_max = budget.max_tokens
            budget.max_tokens = new_max_tokens
            budget.updated_at = datetime.now(timezone.utc)

            # Re-check status after limit change
            if budget.used_tokens >= budget.max_tokens:
                budget.status = "exceeded"
            elif budget.status == "exceeded":
                budget.status = "active"

            self.db.commit()
            self.db.refresh(budget)

            logger.info(
                "budget_limit_updated",
                extra={
                    "company_id": company_id,
                    "budget_type": budget_type,
                    "old_max": old_max,
                    "new_max": new_max_tokens,
                },
            )

            return budget

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("update_limit_failed", extra={"error": str(exc)})
            return None

    # ── Admin: Disable Budget ────────────────────────────────────

    def disable_budget(
        self,
        company_id: str,
        budget_type: str,
        instance_id: Optional[str] = None,
    ) -> Optional[AITokenBudget]:
        """Admin: disable budget tracking for a period."""
        try:
            _validate_company_id(company_id)
            _validate_budget_type(budget_type)

            period = self._get_current_period(budget_type)
            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type=budget_type,
                    budget_period=period,
                    instance_id=instance_id,
                )
                .first()
            )

            if budget is None:
                raise ParwaBaseError(
                    error_code="BUDGET_NOT_FOUND",
                    message=(
                        f"No {budget_type} budget found for company "
                        f"'{company_id}' in period '{period}'"
                    ),
                    status_code=404,
                )

            budget.status = "disabled"
            budget.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(budget)

            logger.info(
                "budget_disabled",
                extra={
                    "company_id": company_id,
                    "budget_type": budget_type,
                },
            )

            return budget

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("disable_budget_failed", extra={"error": str(exc)})
            return None

    # ── Admin: Enable Budget ─────────────────────────────────────

    def enable_budget(
        self,
        company_id: str,
        budget_type: str,
        instance_id: Optional[str] = None,
    ) -> Optional[AITokenBudget]:
        """Admin: re-enable budget tracking."""
        try:
            _validate_company_id(company_id)
            _validate_budget_type(budget_type)

            period = self._get_current_period(budget_type)
            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type=budget_type,
                    budget_period=period,
                    instance_id=instance_id,
                )
                .first()
            )

            if budget is None:
                raise ParwaBaseError(
                    error_code="BUDGET_NOT_FOUND",
                    message=(
                        f"No {budget_type} budget found for company "
                        f"'{company_id}' in period '{period}'"
                    ),
                    status_code=404,
                )

            budget.status = "active"
            budget.updated_at = datetime.now(timezone.utc)

            # Re-check if already exceeded
            if budget.used_tokens >= budget.max_tokens:
                budget.status = "exceeded"

            self.db.commit()
            self.db.refresh(budget)

            logger.info(
                "budget_enabled",
                extra={
                    "company_id": company_id,
                    "budget_type": budget_type,
                },
            )

            return budget

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("enable_budget_failed", extra={"error": str(exc)})
            return None

    # ── Alert Status ─────────────────────────────────────────────

    def get_alert_status(self, company_id: str) -> dict:
        """Check if any alerts need to be sent."""
        try:
            _validate_company_id(company_id)

            budgets = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                )
                .all()
            )

            alerts = []
            for b in budgets:
                alert_level = self._check_alert(b)
                if alert_level != AlertLevel.NONE:
                    alerts.append(
                        {
                            "budget_type": b.budget_type,
                            "budget_period": b.budget_period,
                            "alert_level": alert_level.value,
                            "alert_sent": b.alert_sent,
                            "usage_pct": self._calc_usage_pct(
                                b.used_tokens, b.max_tokens
                            ),
                            "instance_id": b.instance_id,
                        }
                    )

            has_unsent = any(
                a["alert_level"] != AlertLevel.NONE and not a["alert_sent"]
                for a in alerts
            )

            return {
                "company_id": company_id,
                "total_budgets": len(budgets),
                "alerts": alerts,
                "has_unsent_alerts": has_unsent,
            }

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("alert_status_failed", extra={"error": str(exc)})
            return {"error": str(exc)}

    # ── Mark Alert Sent ──────────────────────────────────────────

    def mark_alert_sent(
        self,
        company_id: str,
        budget_type: str,
        instance_id: Optional[str] = None,
    ) -> None:
        """Mark alert as sent for a budget."""
        try:
            _validate_company_id(company_id)
            _validate_budget_type(budget_type)

            period = self._get_current_period(budget_type)
            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type=budget_type,
                    budget_period=period,
                    instance_id=instance_id,
                )
                .first()
            )

            if budget is not None:
                budget.alert_sent = True
                self.db.commit()

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error("mark_alert_failed", extra={"error": str(exc)})

    # ── Admin Overview ───────────────────────────────────────────

    def get_all_tenant_budgets(self) -> list:
        """Admin overview of all tenant budgets."""
        try:
            budgets = self.db.query(AITokenBudget).all()

            result = []
            for b in budgets:
                usage_pct = self._calc_usage_pct(b.used_tokens, b.max_tokens)
                result.append(
                    {
                        "id": b.id,
                        "company_id": b.company_id,
                        "instance_id": b.instance_id,
                        "budget_type": b.budget_type,
                        "budget_period": b.budget_period,
                        "max_tokens": b.max_tokens,
                        "used_tokens": b.used_tokens or 0,
                        "remaining_tokens": max(0, b.max_tokens - (b.used_tokens or 0)),
                        "usage_pct": usage_pct,
                        "status": b.status,
                        "alert_sent": b.alert_sent,
                    }
                )

            return result

        except Exception as exc:
            logger.error("get_all_budgets_failed", extra={"error": str(exc)})
            return []

    # ── Tier-Based Budget Check (Smart Router Integration) ───────

    def check_tier_budget(
        self,
        company_id: str,
        tier: str,
    ) -> BudgetCheckResult:
        """
        Check if a tier has request budget remaining.

        This is the integration point for Smart Router (BC-007).
        The router calls this before selecting a model for a tier.
        If tier budget is exhausted, the router should degrade to a
        lower tier.

        Args:
            company_id: Tenant identifier (BC-001).
            tier: Model tier (light/medium/heavy/guardrail).

        Returns:
            BudgetCheckResult indicating if the tier has capacity.
        """
        try:
            _validate_company_id(company_id)

            tier_lower = tier.lower()
            # Tiers without limits are always allowed
            if tier_lower not in TIER_DAILY_REQUEST_LIMITS:
                return BudgetCheckResult(
                    allowed=True,
                    remaining_tokens=0,
                    usage_pct=0.0,
                    alert_level=AlertLevel.NONE,
                    budget_status=BudgetStatus.ACTIVE,
                    reason=f"Tier '{tier}' has no request limit",
                )

            period = self._get_current_period("daily")
            budget_key = f"tier_{tier_lower}"

            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type="daily",
                    budget_period=period,
                    instance_id=budget_key,
                )
                .first()
            )

            # No budget record — create one with tier limits
            if budget is None:
                budget = self._get_or_create_budget(
                    company_id=company_id,
                    budget_type="daily",
                    budget_period=period,
                    instance_id=budget_key,
                    max_tokens=TIER_DAILY_REQUEST_LIMITS[tier_lower],
                )

            tier_limit = TIER_DAILY_REQUEST_LIMITS[tier_lower]
            remaining = max(0, tier_limit - (budget.used_tokens or 0))
            usage_pct = self._calc_usage_pct(budget.used_tokens or 0, tier_limit)

            if remaining <= 0:
                return BudgetCheckResult(
                    allowed=False,
                    remaining_tokens=0,
                    usage_pct=usage_pct,
                    alert_level=AlertLevel.EXHAUSTED,
                    budget_status=BudgetStatus.EXHAUSTED,
                    reason=f"Tier '{tier}' daily request limit exhausted ({tier_limit})",
                )

            return BudgetCheckResult(
                allowed=True,
                remaining_tokens=remaining,
                usage_pct=usage_pct,
                alert_level=self._check_alert(budget),
                budget_status=BudgetStatus.ACTIVE,
                reason=f"Tier '{tier}' has {remaining} requests remaining today",
            )

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "tier_budget_check_failed",
                extra={"company_id": company_id, "tier": tier, "error": str(exc)},
            )
            # BC-008: Allow on error
            return BudgetCheckResult(
                allowed=True,
                remaining_tokens=0,
                usage_pct=0.0,
                alert_level=AlertLevel.NONE,
                budget_status=BudgetStatus.ACTIVE,
                reason=f"Tier budget check error — allowed (graceful degradation): {
                    str(exc)}",
            )

    def record_tier_usage(
        self,
        company_id: str,
        tier: str,
        tokens_used: int = 1,
    ) -> None:
        """
        Record a single request against a tier's daily budget.
        Called by Smart Router after each successful LLM call.

        Args:
            company_id: Tenant identifier (BC-001).
            tier: Model tier that was used.
            tokens_used: Count of requests (default 1 per call).
        """
        try:
            tier_lower = tier.lower()
            if tier_lower not in TIER_DAILY_REQUEST_LIMITS:
                return

            period = self._get_current_period("daily")
            budget_key = f"tier_{tier_lower}"

            budget = (
                self.db.query(AITokenBudget)
                .filter_by(
                    company_id=company_id,
                    budget_type="daily",
                    budget_period=period,
                    instance_id=budget_key,
                )
                .first()
            )

            if budget is None:
                budget = self._get_or_create_budget(
                    company_id=company_id,
                    budget_type="daily",
                    budget_period=period,
                    instance_id=budget_key,
                    max_tokens=TIER_DAILY_REQUEST_LIMITS[tier_lower],
                )

            budget.used_tokens = (budget.used_tokens or 0) + tokens_used
            budget.updated_at = datetime.now(timezone.utc)

            if budget.used_tokens >= budget.max_tokens:
                budget.status = "exceeded"

            self.db.commit()

            logger.debug(
                "tier_usage_recorded",
                extra={
                    "company_id": company_id,
                    "tier": tier_lower,
                    "used": budget.used_tokens,
                    "max": budget.max_tokens,
                },
            )

        except Exception as exc:
            logger.error(
                "tier_usage_record_failed",
                extra={"company_id": company_id, "tier": tier, "error": str(exc)},
            )
            # BC-008: Don't crash

    # ══════════════════════════════════════════════════════════════
    # PRIVATE HELPERS
    # ══════════════════════════════════════════════════════════════

    def _get_current_period(self, budget_type: str) -> str:
        """Return '2026-04-08' for daily, '2026-04' for monthly. UTC. BC-012."""
        now = datetime.now(timezone.utc)
        if budget_type == "daily":
            return now.strftime("%Y-%m-%d")
        elif budget_type == "monthly":
            return now.strftime("%Y-%m")
        else:
            raise ParwaBaseError(
                error_code="INVALID_BUDGET_TYPE",
                message=f"Unknown budget_type: {budget_type}",
                status_code=400,
            )

    def _get_or_create_budget(
        self,
        company_id: str,
        budget_type: str,
        budget_period: str,
        instance_id: Optional[str],
        max_tokens: int,
    ) -> AITokenBudget:
        """Get existing budget or create a new one. Idempotent."""
        existing = (
            self.db.query(AITokenBudget)
            .filter_by(
                company_id=company_id,
                budget_type=budget_type,
                budget_period=budget_period,
                instance_id=instance_id,
            )
            .first()
        )

        if existing is not None:
            return existing

        budget = AITokenBudget(
            company_id=company_id,
            instance_id=instance_id,
            budget_type=budget_type,
            budget_period=budget_period,
            max_tokens=max_tokens,
            used_tokens=0,
            alert_threshold_pct=80,
            alert_sent=False,
            hard_stop=True,
            status="active",
            variant_default_limits=json.dumps(DEFAULT_VARIANT_LIMITS),
        )
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def _check_alert(self, budget: AITokenBudget) -> AlertLevel:
        """Check alert thresholds on a budget record."""
        if budget.used_tokens is None or budget.max_tokens == 0:
            return AlertLevel.NONE

        pct = self._calc_usage_pct(budget.used_tokens, budget.max_tokens)

        if pct >= 100:
            return AlertLevel.EXHAUSTED
        elif pct >= 95:
            return AlertLevel.CRITICAL
        elif pct >= 80:
            return AlertLevel.WARNING
        return AlertLevel.NONE

    def _get_variant_limits(self, variant_type: str) -> dict:
        """Get default limits for a variant type."""
        _validate_variant_type(variant_type)
        return DEFAULT_VARIANT_LIMITS[variant_type]

    @staticmethod
    def _calc_usage_pct(used: int, max_val: int) -> float:
        """Calculate usage percentage. Returns 0.0-100.0."""
        if not isinstance(used, int) or not isinstance(max_val, int):
            return 0.0
        if max_val <= 0:
            return 0.0
        return round((used / max_val) * 100, 2)
