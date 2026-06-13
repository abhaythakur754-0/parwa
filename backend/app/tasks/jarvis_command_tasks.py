"""
PARWA Jarvis Command Celery Tasks (Phase 3 Command Layer)

Celery tasks that enable asynchronous command execution and
periodic maintenance for the command layer:
  1. execute_command_async: Execute a command in the background
     (for long-running commands like report generation)
  2. prune_command_history: Periodic cleanup of old command
     records (runs every 6 hours via Celery Beat)

Architecture:
  API / WebSocket → execute_command_async
      → jarvis_command_service.execute_command()
      → Returns structured result dict

  Celery Beat (6h) → prune_command_history
      → For each active session:
          → jarvis_command_service.prune_old_commands()

BC-001: company_id first parameter on public methods.
BC-004: All tasks use ParwaBaseTask with retry config.
BC-008: Every task wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.tasks.base import ParwaBaseTask, set_task_tenant_header
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.jarvis_command_tasks")


# ══════════════════════════════════════════════════════════════════
# ASYNC COMMAND EXECUTION: Offload long-running commands
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.jarvis_command_tasks.execute_command_async",
    max_retries=2,
    retry_backoff=True,
)
def execute_command_async(
    self,
    company_id: str,
    command_id: str,
    session_id: str,
    user_id: str,
):
    """Execute a command asynchronously via Celery.

    Used for commands that may take longer to complete, such as
    report generation, bulk data operations, or external API calls.
    The task dispatches the command through the command service and
    returns a structured result dict.

    Flow:
      1. Open DB session
      2. Call jarvis_command_service.execute_command()
      3. Commit and return result dict

    Args:
        company_id: Company ID for BC-001 tenant isolation.
        command_id: The JarvisCommand ID to execute.
        session_id: Session ID the command belongs to.
        user_id: User ID for security scoping.

    Returns:
        Dict with status, command_id, and execution result or error.
    """
    try:
        from database.base import SessionLocal
        from app.services import jarvis_command_service

        db = SessionLocal()
        try:
            result = jarvis_command_service.execute_command(
                db=db,
                company_id=company_id,
                command_id=command_id,
                session_id=session_id,
                user_id=user_id,
            )

            db.commit()

            logger.info(
                "command_async_executed: company=%s, command=%s, session=%s",
                company_id, command_id, session_id,
            )

            return {
                "status": "ok",
                "command_id": command_id,
                "session_id": session_id,
                "company_id": company_id,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            }

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception as exc:
        logger.warning(
            "command_async_execution_failed: company=%s, command=%s, "
            "session=%s, error=%s",
            company_id, command_id, session_id, str(exc)[:200],
        )
        return {
            "status": "failed",
            "command_id": command_id,
            "session_id": session_id,
            "company_id": company_id,
            "error": str(exc)[:200],
        }


# ══════════════════════════════════════════════════════════════════
# MAINTENANCE: Prune old command records
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.jarvis_command_tasks.prune_command_history",
    max_retries=1,
)
def prune_command_history(self):
    """Periodic cleanup of old command records.

    Runs every 6 hours via Celery Beat. Iterates over all
    active Jarvis sessions and prunes old command records
    beyond the configured retention limit per session.

    Flow:
      1. Query all active sessions
      2. For each session, call jarvis_command_service.prune_old_commands()
      3. Return summary of pruned records

    Returns:
        Dict with status, sessions processed, and total pruned count.
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis import JarvisSession
        from app.services import jarvis_command_service

        db = SessionLocal()
        try:
            active_sessions = (
                db.query(JarvisSession)
                .filter(JarvisSession.is_active.is_(True))
                .all()
            )

            total_pruned = 0
            sessions_processed = 0
            sessions_failed = 0

            for session in active_sessions:
                try:
                    session_id = str(session.id)
                    company_id = str(session.company_id)

                    pruned = jarvis_command_service.prune_old_commands(
                        db=db,
                        session_id=session_id,
                        company_id=company_id,
                        max_keep=100,
                    )
                    total_pruned += pruned
                    sessions_processed += 1

                except Exception:
                    sessions_failed += 1
                    logger.debug(
                        "prune_commands_session_failed: session=%s",
                        str(session.id),
                        exc_info=True,
                    )

            db.commit()

            logger.info(
                "command_prune_complete: sessions=%d, processed=%d, "
                "failed=%d, total_pruned=%d",
                len(active_sessions), sessions_processed,
                sessions_failed, total_pruned,
            )

            return {
                "status": "ok",
                "total_sessions": len(active_sessions),
                "sessions_processed": sessions_processed,
                "sessions_failed": sessions_failed,
                "total_pruned": total_pruned,
                "pruned_at": datetime.now(timezone.utc).isoformat(),
            }

        finally:
            db.close()

    except Exception as exc:
        logger.warning(
            "command_prune_failed: error=%s",
            str(exc)[:200],
        )
        return {"status": "failed", "error": str(exc)[:200]}
