"""
PARWA AI Engine Celery Tasks (Week 8 Day 1-2, BC-004)

Background tasks for AI Engine operations:
- rebalance_workload: Periodic workload rebalancer (every 60s)
- reset_daily_budgets: Daily token budget reset (midnight UTC)
- warmup_tenant_models: Cold start warmup for tenant activation
- cleanup_stale_injection_logs: Clean old prompt injection logs (daily)

Building Codes:
- BC-001: Multi-Tenant Isolation (company_id on every task)
- BC-004: Background Jobs (Celery patterns)
- BC-008: Graceful degradation
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.ai_engine")


# ══════════════════════════════════════════════════════════════════
# 1. REBALANCE WORKLOAD (every 60s via beat)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.ai_engine_tasks.rebalance_workload",
    max_retries=2,
    soft_time_limit=30,
    time_limit=60,
)
def rebalance_workload(self, company_id: Optional[str] = None) -> dict:
    """Periodic workload rebalancer across variant instances.

    If company_id provided: rebalance that specific company.
    If None: rebalance ALL companies.

    Calls into variant_orchestration_service.rebalance_workload().
    """
    try:
        from database.base import SessionLocal
        from app.services.variant_orchestration_service import (
            rebalance_workload as _rebalance,
        )

        db = SessionLocal()
        try:
            if company_id:
                result = _rebalance(db, company_id)
                logger.info(
                    "rebalance_workload_success",
                    extra={
                        "task": self.name,
                        "company_id": company_id,
                        "rebalanced_instances": result.get(
                            "rebalanced_instances",
                            0,
                        ),
                        "migrated_tickets": result.get(
                            "migrated_tickets",
                            0,
                        ),
                    },
                )
            else:
                # Rebalance ALL companies
                from database.models.variant_engine import VariantInstance

                companies = (
                    db.query(
                        VariantInstance.company_id,
                    )
                    .distinct()
                    .all()
                )

                total_rebalanced = 0
                total_migrated = 0
                for (cid,) in companies:
                    try:
                        result = _rebalance(db, cid)
                        total_rebalanced += result.get(
                            "rebalanced_instances",
                            0,
                        )
                        total_migrated += result.get(
                            "migrated_tickets",
                            0,
                        )
                    except Exception as exc:
                        logger.warning(
                            "rebalance_company_failed",
                            extra={
                                "task": self.name,
                                "company_id": cid,
                                "error": str(exc)[:200],
                            },
                        )
                        # BC-008: Continue with next company

                logger.info(
                    "rebalance_all_companies_success",
                    extra={
                        "task": self.name,
                        "companies_scanned": len(companies),
                        "total_rebalanced_instances": total_rebalanced,
                        "total_migrated_tickets": total_migrated,
                    },
                )

            return {
                "status": "rebalanced",
                "company_id": company_id,
            }
        finally:
            db.close()

    except Exception as exc:
        logger.error(
            "rebalance_workload_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 2. RESET DAILY BUDGETS (midnight UTC via beat)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.ai_engine_tasks.reset_daily_budgets",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
def reset_daily_budgets(self) -> dict:
    """Reset used_tokens to 0 for all daily budgets.

    Resets the alert_sent flag so alerts can trigger again.
    Called daily at midnight UTC via beat.

    Resets budgets for ALL companies.
    """
    try:
        from database.base import SessionLocal
        from database.models.variant_engine import AITokenBudget

        db = SessionLocal()
        try:
            budgets = (
                db.query(AITokenBudget)
                .filter_by(
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

            db.commit()

            logger.info(
                "reset_daily_budgets_success",
                extra={
                    "task": self.name,
                    "budgets_reset": reset_count,
                },
            )

            return {
                "status": "reset",
                "budgets_reset": reset_count,
            }
        finally:
            db.close()

    except Exception as exc:
        logger.error(
            "reset_daily_budgets_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 3. WARMUP TENANT MODELS (on-demand, queue: ai_light)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="ai_light",
    name="app.tasks.ai_engine_tasks.warmup_tenant_models",
    max_retries=2,
    soft_time_limit=30,
    time_limit=60,
)
@with_company_id
def warmup_tenant_models(
    self,
    company_id: str,
    variant_type: str = "mini_parwa",
) -> dict:
    """Cold start warmup for tenant activation or variant upgrade.

    Pre-warms common model+technique combos for the tenant's
    variant type. Calls into cold_start_service.warmup_tenant().

    Args:
        company_id: Tenant identifier (BC-001).
        variant_type: Variant type to warm models for.
    """
    try:
        from app.core.cold_start_service import (
            get_cold_start_service,
        )

        svc = get_cold_start_service()
        state = svc.warmup_tenant(company_id, variant_type)

        logger.info(
            "warmup_tenant_models_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "variant_type": variant_type,
                "overall_status": state.overall_status.value,
                "models_warmed": len(state.models_warmed),
                "time_to_warm_ms": state.time_to_warm_ms,
                "fallback_used": state.fallback_used,
            },
        )

        return {
            "status": "warmed",
            "company_id": company_id,
            "variant_type": variant_type,
            "overall_status": state.overall_status.value,
            "models_warmed": len(state.models_warmed),
            "time_to_warm_ms": state.time_to_warm_ms,
            "fallback_used": state.fallback_used,
        }

    except Exception as exc:
        logger.error(
            "warmup_tenant_models_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "variant_type": variant_type,
                "error": str(exc)[:200],
            },
        )
        raise


# ══════════════════════════════════════════════════════════════════
# 4. CLEANUP STALE INJECTION LOGS (daily at 04:00 UTC)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.ai_engine_tasks.cleanup_stale_injection_logs",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def cleanup_stale_injection_logs(self, days: int = 90) -> dict:
    """Delete prompt_injection_attempts older than N days.

    Runs daily at 04:00 UTC via beat. Default retention: 90 days.

    Args:
        days: Number of days to retain logs. Older records deleted.
    """
    try:
        from database.base import SessionLocal
        from database.models.variant_engine import PromptInjectionAttempt

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        db = SessionLocal()
        try:
            deleted = (
                db.query(PromptInjectionAttempt)
                .filter(PromptInjectionAttempt.created_at < cutoff)
                .delete(synchronize_session="fetch")
            )
            db.commit()

            logger.info(
                "cleanup_stale_injection_logs_success",
                extra={
                    "task": self.name,
                    "days": days,
                    "records_deleted": deleted,
                    "cutoff": cutoff.isoformat(),
                },
            )

            return {
                "status": "cleaned",
                "days": days,
                "records_deleted": deleted,
                "cutoff": cutoff.isoformat(),
            }
        finally:
            db.close()

    except Exception as exc:
        logger.error(
            "cleanup_stale_injection_logs_failed",
            extra={
                "task": self.name,
                "days": days,
                "error": str(exc)[:200],
            },
        )
        raise
