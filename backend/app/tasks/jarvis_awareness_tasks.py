"""
PARWA Jarvis Awareness Celery Tasks (Phase 2.4)

Celery tasks that make the awareness engine run automatically:
  1. Periodic tick: Runs every 30 seconds per active CC session
  2. Proactive injection: After tick, injects critical alerts into chat
  3. Event dispatch: Publishes real-time events via Redis Pub/Sub

Architecture:
  Celery Beat → run_awareness_ticks_all_sessions
      → For each active CC session:
          → run_awareness_tick_single_session
              → jarvis_awareness_engine.run_awareness_tick()
              → jarvis_proactive_injector.inject_tick_summary()
              → jarvis_event_dispatcher.dispatch_tick_event()

BC-001: company_id first parameter on public methods.
BC-004: All tasks use ParwaBaseTask with retry config.
BC-008: Every task wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.tasks.base import ParwaBaseTask, set_task_tenant_header
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.jarvis_awareness_tasks")


# ══════════════════════════════════════════════════════════════════
# PERIODIC TICK: Runs every 30 seconds for all active CC sessions
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.jarvis_awareness_tasks.run_awareness_ticks_all",
    max_retries=1,
)
def run_awareness_ticks_all(self):
    """Dispatch awareness tick tasks for all active CC sessions.

    This is the Celery Beat entry point. It finds all active
    customer_care sessions and dispatches a per-session tick
    task for each.

    Flow:
      1. Query all active customer_care sessions
      2. For each session, dispatch run_awareness_tick_single
      3. Return summary of dispatched sessions
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis import JarvisSession

        db = SessionLocal()
        try:
            # Find all active customer_care sessions with awareness enabled
            active_sessions = (
                db.query(JarvisSession)
                .filter(
                    JarvisSession.type == "customer_care",
                    JarvisSession.is_active.is_(True),
                )
                .all()
            )

            dispatched = 0
            skipped = 0

            for session in active_sessions:
                # Check if awareness is enabled in session context
                try:
                    ctx = json.loads(session.context_json) if session.context_json else {}
                except (json.JSONDecodeError, TypeError):
                    ctx = {}

                # Only tick sessions where awareness is enabled
                # or where the user has ever triggered a manual tick
                if not ctx.get("awareness_enabled", False):
                    # Check if the session has any snapshots (from manual tick)
                    from database.models.jarvis_cc import JarvisAwarenessSnapshot
                    has_snapshots = (
                        db.query(JarvisAwarenessSnapshot.id)
                        .filter(
                            JarvisAwarenessSnapshot.session_id == str(session.id),
                            JarvisAwarenessSnapshot.company_id == str(session.company_id),
                        )
                        .limit(1)
                        .first()
                    )
                    if not has_snapshots:
                        skipped += 1
                        continue

                # Dispatch per-session tick task
                headers = set_task_tenant_header(str(session.company_id))
                run_awareness_tick_single.apply_async(
                    kwargs={
                        "company_id": str(session.company_id),
                        "session_id": str(session.id),
                        "user_id": str(session.user_id),
                    },
                    headers=headers,
                )
                dispatched += 1

            logger.info(
                "awareness_ticks_dispatched: total_active=%d, dispatched=%d, skipped=%d",
                len(active_sessions), dispatched, skipped,
            )

            return {
                "status": "ok",
                "total_active": len(active_sessions),
                "dispatched": dispatched,
                "skipped": skipped,
            }

        finally:
            db.close()

    except Exception as exc:
        logger.warning(
            "awareness_ticks_dispatch_failed: error=%s",
            str(exc)[:200],
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.jarvis_awareness_tasks.run_awareness_tick_single",
    max_retries=2,
    retry_backoff=True,
)
def run_awareness_tick_single(
    self,
    company_id: str,
    session_id: str,
    user_id: str,
):
    """Run a single awareness tick for one CC session.

    This is the per-session task dispatched by run_awareness_ticks_all.
    It:
      1. Runs the awareness tick (collect state, check rules, create alerts)
      2. Injects eligible alerts into the CC chat
      3. Dispatches real-time events via Redis

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        user_id: User ID for security scoping.
    """
    try:
        from database.base import SessionLocal
        from app.services import jarvis_awareness_engine
        from app.services import jarvis_proactive_injector
        from app.services import jarvis_event_dispatcher

        db = SessionLocal()
        try:
            # Step 1: Run the awareness tick
            tick_result = jarvis_awareness_engine.run_awareness_tick(
                db=db,
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                tick_type="periodic",
            )

            # Step 2: Get created alerts for injection
            alert_ids = tick_result.get("alert_ids", [])
            alerts_created = []
            if alert_ids:
                from database.models.jarvis_cc import JarvisProactiveAlert
                alerts_created = (
                    db.query(JarvisProactiveAlert)
                    .filter(JarvisProactiveAlert.id.in_(alert_ids))
                    .all()
                )

            # Step 3: Inject eligible alerts into CC chat
            injected = jarvis_proactive_injector.inject_tick_summary(
                db=db,
                session_id=session_id,
                company_id=company_id,
                tick_result=tick_result,
                alerts_created=alerts_created,
            )

            # Step 4: Dispatch events via Redis
            try:
                # Tick event
                jarvis_event_dispatcher.dispatch_tick_event(
                    company_id=company_id,
                    session_id=session_id,
                    tick_number=tick_result.get("tick_number", 0),
                    tick_type="periodic",
                    system_health=tick_result.get("system_health", "unknown"),
                    alerts_created=tick_result.get("alerts_created", 0),
                    quality_score=tick_result.get("quality_score"),
                    drift_score=tick_result.get("drift_score"),
                )

                # Alert events
                for alert in alerts_created:
                    jarvis_event_dispatcher.dispatch_alert_event(
                        company_id=company_id,
                        session_id=session_id,
                        alert_id=str(alert.id),
                        alert_type=alert.alert_type,
                        severity=alert.severity,
                        title=alert.title,
                        action="created",
                    )
            except Exception:
                logger.debug("event_dispatch_non_fatal", exc_info=True)

            db.commit()

            return {
                "status": "ok",
                "session_id": session_id,
                "tick_number": tick_result.get("tick_number", 0),
                "alerts_created": tick_result.get("alerts_created", 0),
                "alerts_injected": len(injected),
                "system_health": tick_result.get("system_health", "unknown"),
            }

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception as exc:
        logger.warning(
            "awareness_tick_single_failed: session=%s, error=%s",
            session_id, str(exc)[:200],
        )
        return {"status": "failed", "session_id": session_id, "error": str(exc)[:200]}


# ══════════════════════════════════════════════════════════════════
# ON-DEMAND TICK: Triggered manually or on_change
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="ai_light",
    name="app.tasks.jarvis_awareness_tasks.trigger_on_change_tick",
    max_retries=2,
)
def trigger_on_change_tick(
    self,
    company_id: str,
    session_id: str,
    user_id: str,
    changed_field: str = "",
):
    """Trigger an on_change awareness tick.

    Called when a monitored field changes significantly
    (e.g., emergency state toggled, quality score drops).

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        user_id: User ID.
        changed_field: The field that triggered the on_change tick.
    """
    try:
        from database.base import SessionLocal
        from app.services import jarvis_awareness_engine
        from app.services import jarvis_proactive_injector
        from app.services import jarvis_event_dispatcher

        db = SessionLocal()
        try:
            tick_result = jarvis_awareness_engine.run_awareness_tick(
                db=db,
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                tick_type="on_change",
            )

            # Get alerts
            alert_ids = tick_result.get("alert_ids", [])
            alerts_created = []
            if alert_ids:
                from database.models.jarvis_cc import JarvisProactiveAlert
                alerts_created = (
                    db.query(JarvisProactiveAlert)
                    .filter(JarvisProactiveAlert.id.in_(alert_ids))
                    .all()
                )

            # Inject
            jarvis_proactive_injector.inject_tick_summary(
                db=db,
                session_id=session_id,
                company_id=company_id,
                tick_result=tick_result,
                alerts_created=alerts_created,
            )

            # Dispatch state event
            if changed_field:
                jarvis_event_dispatcher.dispatch_state_event(
                    company_id=company_id,
                    session_id=session_id,
                    field=changed_field,
                    old_value=None,
                    new_value=None,
                    change_type="on_change_triggered",
                )

            db.commit()

            return {
                "status": "ok",
                "session_id": session_id,
                "trigger": changed_field,
                "tick_number": tick_result.get("tick_number", 0),
            }

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception as exc:
        logger.warning(
            "on_change_tick_failed: session=%s, field=%s, error=%s",
            session_id, changed_field, str(exc)[:200],
        )
        return {"status": "failed", "error": str(exc)[:200]}


# ══════════════════════════════════════════════════════════════════
# MAINTENANCE: Prune old snapshots and expired alerts
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.jarvis_awareness_tasks.prune_awareness_data",
    max_retries=1,
)
def prune_awareness_data(self):
    """Periodic cleanup of old awareness snapshots and expired alerts.

    Runs every 6 hours via Celery Beat. Prunes:
      - Snapshots older than MAX_SNAPSHOTS_PER_SESSION per session
      - Expired alerts (past their TTL)
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis import JarvisSession
        from app.services import jarvis_awareness_engine

        db = SessionLocal()
        try:
            # Find all active CC sessions with awareness
            active_sessions = (
                db.query(JarvisSession)
                .filter(
                    JarvisSession.type == "customer_care",
                    JarvisSession.is_active.is_(True),
                )
                .all()
            )

            total_snapshots_pruned = 0
            total_alerts_expired = 0

            for session in active_sessions:
                try:
                    session_id = str(session.id)
                    company_id = str(session.company_id)

                    pruned = jarvis_awareness_engine.prune_old_snapshots(
                        db=db,
                        session_id=session_id,
                        company_id=company_id,
                    )
                    total_snapshots_pruned += pruned

                    expired = jarvis_awareness_engine.prune_expired_alerts(
                        db=db,
                        session_id=session_id,
                        company_id=company_id,
                    )
                    total_alerts_expired += expired

                except Exception:
                    logger.debug(
                        "prune_session_failed: session=%s",
                        str(session.id),
                        exc_info=True,
                    )

            db.commit()

            logger.info(
                "awareness_prune_complete: sessions=%d, snapshots_pruned=%d, "
                "alerts_expired=%d",
                len(active_sessions),
                total_snapshots_pruned,
                total_alerts_expired,
            )

            return {
                "status": "ok",
                "sessions_processed": len(active_sessions),
                "snapshots_pruned": total_snapshots_pruned,
                "alerts_expired": total_alerts_expired,
            }

        finally:
            db.close()

    except Exception as exc:
        logger.warning(
            "awareness_prune_failed: error=%s",
            str(exc)[:200],
        )
        return {"status": "failed", "error": str(exc)[:200]}
