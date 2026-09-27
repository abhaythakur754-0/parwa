"""Business logic service for Superglue Action Safety.

This is the ONLY place that creates/updates SuperglueActionSafety DB records.
The API layer (superglue_actions.py) delegates here. The MCP adapter reads from DB.

BC-001: all queries scoped to company_id.
BC-008: every method wrapped, never crashes the caller.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from app.core.action_safety import ActionSafetyLevel, classify_action, needs_approval
from app.core.regulatory_guardrails import get_applicable_frameworks


def classify_and_persist(
    company_id: str,
    tool_id: str,
    tool_name: str,
    tool_description: str = "",
    output_schema: Optional[dict] = None,
    db_session=None,
) -> dict:
    """Classify a tool, persist the result to DB, and return as dict.

    Returns a dict matching ActionSafetyResponse schema.
    BC-008: returns a safe default dict on any error.
    """
    try:
        result = classify_action(tool_id, tool_description or tool_name)
        frameworks = get_applicable_frameworks(result.level.value)
        approval = needs_approval(result.level)

        record = {
            "id": _uuid(),
            "company_id": company_id,
            "tool_id": tool_id,
            "tool_name": tool_name,
            "safety_level": result.level.value,
            "needs_approval": approval,
            "regulatory_frameworks": json.dumps(frameworks),
            "output_schema": json.dumps(output_schema) if output_schema else None,
            "is_active": True,
            "classified_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        if db_session is not None:
            try:
                import sqlalchemy
                db_session.execute(
                    sqlalchemy.text(
                        "DELETE FROM superglue_action_safety WHERE company_id = :cid AND tool_id = :tid"
                    ),
                    {"cid": company_id, "tid": tool_id},
                )
                db_session.execute(
                    sqlalchemy.text(
                        "INSERT INTO superglue_action_safety "
                        "(id, company_id, tool_id, tool_name, safety_level, needs_approval, "
                        "regulatory_frameworks, output_schema, is_active, classified_at, updated_at) "
                        "VALUES (:id, :company_id, :tool_id, :tool_name, :safety_level, :needs_approval, "
                        ":regulatory_frameworks, :output_schema, :is_active, :classified_at, :updated_at)"
                    ),
                    record,
                )
                db_session.commit()
            except Exception:
                if db_session:
                    db_session.rollback()

        return {
            "id": record["id"],
            "tool_id": tool_id,
            "tool_name": tool_name,
            "safety_level": result.level.value,
            "needs_approval": approval,
            "regulatory_frameworks": frameworks,
            "is_active": True,
        }
    except Exception:
        return {
            "id": "", "tool_id": tool_id, "tool_name": tool_name,
            "safety_level": "read", "needs_approval": False,
            "regulatory_frameworks": [], "is_active": True,
        }


def get_classification(company_id: str, tool_id: str, db_session=None) -> Optional[dict]:
    """Get a persisted classification for a tool. BC-001: scoped to company_id."""
    try:
        if db_session is None:
            return None
        import sqlalchemy
        row = db_session.execute(
            sqlalchemy.text(
                "SELECT id, tool_id, tool_name, safety_level, needs_approval, "
                "regulatory_frameworks, is_active FROM superglue_action_safety "
                "WHERE company_id = :cid AND tool_id = :tid AND is_active = TRUE"
            ),
            {"cid": company_id, "tid": tool_id},
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0], "tool_id": row[1], "tool_name": row[2],
            "safety_level": row[3], "needs_approval": row[4],
            "regulatory_frameworks": json.loads(row[5]) if row[5] else [],
            "is_active": row[6],
        }
    except Exception:
        return None


def list_classifications(
    company_id: str, safety_level: Optional[str] = None,
    active_only: bool = False, db_session=None,
) -> list[dict]:
    """List classifications for a company. BC-001: scoped to company_id."""
    try:
        if db_session is None:
            return []
        import sqlalchemy
        sql = ("SELECT id, tool_id, tool_name, safety_level, needs_approval, "
               "regulatory_frameworks, is_active FROM superglue_action_safety "
               "WHERE company_id = :cid")
        params: dict = {"cid": company_id}
        if safety_level:
            sql += " AND safety_level = :sl"
            params["sl"] = safety_level
        if active_only:
            sql += " AND is_active = TRUE"
        sql += " ORDER BY classified_at DESC"
        rows = db_session.execute(sqlalchemy.text(sql), params).fetchall()
        return [
            {"id": r[0], "tool_id": r[1], "tool_name": r[2],
             "safety_level": r[3], "needs_approval": r[4],
             "regulatory_frameworks": json.loads(r[5]) if r[5] else [],
             "is_active": r[6]}
            for r in rows
        ]
    except Exception:
        return []


def toggle_override(company_id: str, tool_id: str, override: bool, db_session=None) -> Optional[dict]:
    """Toggle approval_required_override. BC-001: scoped to company_id."""
    try:
        if db_session is None:
            return None
        import sqlalchemy
        db_session.execute(
            sqlalchemy.text(
                "UPDATE superglue_action_safety SET approval_required_override = :ov, "
                "updated_at = :now WHERE company_id = :cid AND tool_id = :tid"
            ),
            {"ov": override, "now": datetime.now(timezone.utc), "cid": company_id, "tid": tool_id},
        )
        db_session.commit()
        return get_classification(company_id, tool_id, db_session)
    except Exception:
        if db_session:
            db_session.rollback()
        return None


def _uuid() -> str:
    import uuid
    return str(uuid.uuid4())
