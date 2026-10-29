#!/usr/bin/env python3
"""
PARWA Tool Registry — DB persistence for factory-built & self-built tools.

Answers two production questions with plain SQL:
  1. "Which tools belong to which agent?"      → ai_agent_assignments
  2. "Which tools does this tenant have?"      → superglue_action_safety

This module is BEST-EFFORT by design: if the database is unreachable
(e.g. Supabase creds expired), every function returns {'ok': False, ...}
and the caller (tool factory / self-extension loop) continues — Superglue
remains the source of truth for tool execution; the DB is the searchable
registry + audit trail.

Tables written (both already exist in backend/database/models/):
  - superglue_action_safety  → per-tool inventory + safety classification
  - ai_agent_assignments     → agent ↔ tool link (node_1 routes by
                               capabilities; node_5 executes superglue_tool_id)

Env:
  DATABASE_URL (or PARWA_DATABASE_URL) — SQLAlchemy URL.
  SQLite for local tests; Supabase Postgres in production.

CLI (smoke test):
  python3 tool_registry_db.py --smoke-test
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _get_engine_and_models():
    """Late-bind engine + models so import errors become clean 'ok: False'."""
    url = os.environ.get("PARWA_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return None, None, None, "no DATABASE_URL / PARWA_DATABASE_URL set"
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
    sys.path.insert(0, os.path.abspath(backend_dir))
    try:
        from sqlalchemy import create_engine  # noqa: E402
        from database.models.superglue_action_safety import SuperglueActionSafety  # noqa: E402
        from database.models.variant_engine import AIAgentAssignment  # noqa: E402
        from database.base import Base  # noqa: E402
    except Exception as e:  # noqa: BLE001
        return None, None, None, f"import failed: {e}"
    try:
        eng = create_engine(url, pool_pre_ping=True, future=True)
        # best-effort: ensure tables exist (no-op when they already do)
        Base.metadata.create_all(
            eng,
            tables=[
                Base.metadata.tables["superglue_action_safety"],
                Base.metadata.tables["ai_agent_assignments"],
            ],
        )
        return eng, SuperglueActionSafety, AIAgentAssignment, None
    except Exception as e:  # noqa: BLE001
        return None, None, None, f"engine failed: {e}"


def register_tool(
    company_id: str,
    tool_id: str,
    tool_name: str,
    risk: str = "read",
    approval_required: bool = False,
    capability: str | None = None,
    created_by: str = "tool_factory",
    origin: str = "preset_deploy",
    created_for_ticket: str | None = None,
    tool_definition: dict | None = None,
) -> dict:
    """Upsert tool inventory (superglue_action_safety) + agent link
    (ai_agent_assignments). Best-effort; never raises."""
    eng, Safety, Assignment, err = _get_engine_and_models()
    if eng is None:
        return {"ok": False, "error": err, "tool_id": tool_id}
    now = datetime.now(timezone.utc)
    try:
        from sqlalchemy import select

        with eng.begin() as conn:
            # 1. Tool inventory row (upsert by (company_id, tool_id))
            row = conn.execute(
                select(Safety).where(
                    Safety.company_id == company_id, Safety.tool_id == tool_id
                )
            ).scalar_one_or_none()
            if row is None:
                conn.execute(
                    Safety.__table__.insert().values(
                        company_id=company_id,
                        tool_id=tool_id,
                        tool_name=tool_name,
                        safety_level=risk,          # 'read' | 'write'
                        needs_approval=approval_required,
                        is_active=True,
                        classified_at=now,
                        updated_at=now,
                    )
                )
                action = "inserted"
            else:
                conn.execute(
                    Safety.__table__.update()
                    .where(Safety.company_id == company_id, Safety.tool_id == tool_id)
                    .values(
                        tool_name=tool_name,
                        safety_level=risk,
                        needs_approval=approval_required,
                        is_active=True,
                        updated_at=now,
                    )
                )
                action = "updated"

            # 2. Agent ↔ tool link (upsert one assignment per (company, tool))
            agent_name = f"Self-Extended Agent: {capability or tool_name}"
            arow = conn.execute(
                select(Assignment).where(
                    Assignment.company_id == company_id,
                    Assignment.superglue_tool_id == tool_id,
                )
            ).scalar_one_or_none()
            if arow is None:
                conn.execute(
                    Assignment.__table__.insert().values(
                        company_id=company_id,
                        agent_name=agent_name[:100],
                        agent_role="action",
                        domain=(capability or "general")[:100],
                        capabilities=json.dumps([capability] if capability else []),
                        instructions=(
                            f"Tool auto-{'created by self-extension loop' if origin == 'self_extension' else 'deployed by tool factory'}"
                            f"{' for ticket ' + created_for_ticket if created_for_ticket else ''}. "
                            f"origin={origin}, created_by={created_by}."
                        ),
                        status="active",
                        superglue_tool_id=tool_id,
                        superglue_tool_status="active",
                        superglue_tool_definition=(
                            json.dumps(tool_definition, default=str)[:8000]
                            if tool_definition else None
                        ),
                        superglue_tool_created_at=now,
                        approval_required=approval_required,
                        approval_threshold_cents=0,
                    )
                )
                link_action = "inserted"
            else:
                conn.execute(
                    Assignment.__table__.update()
                    .where(
                        Assignment.company_id == company_id,
                        Assignment.superglue_tool_id == tool_id,
                    )
                    .values(
                        superglue_tool_status="active",
                        superglue_tool_definition=(
                            json.dumps(tool_definition, default=str)[:8000]
                            if tool_definition else arow.superglue_tool_definition
                        ),
                        approval_required=approval_required,
                    )
                )
                link_action = "updated"
        return {
            "ok": True,
            "tool_id": tool_id,
            "inventory": action,
            "agent_link": link_action,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:300], "tool_id": tool_id}


def list_tools_for_tenant(company_id: str) -> list[dict]:
    """All registered tools for a tenant (DB view)."""
    eng, Safety, _, err = _get_engine_and_models()
    if eng is None:
        return [{"error": err}]
    try:
        from sqlalchemy import select

        with eng.connect() as conn:
            rows = conn.execute(
                select(
                    Safety.tool_id, Safety.tool_name,
                    Safety.safety_level, Safety.needs_approval, Safety.is_active,
                ).where(Safety.company_id == company_id)
            ).fetchall()
        return [
            {
                "tool_id": r[0], "tool_name": r[1], "risk": r[2],
                "needs_approval": r[3], "is_active": r[4],
            }
            for r in rows
        ]
    except Exception as e:  # noqa: BLE001
        return [{"error": str(e)[:300]}]


def list_agents_with_tools(company_id: str) -> list[dict]:
    """Which agent owns which tool (DB view)."""
    eng, _, Assignment, err = _get_engine_and_models()
    if eng is None:
        return [{"error": err}]
    try:
        from sqlalchemy import select

        with eng.connect() as conn:
            rows = conn.execute(
                select(
                    Assignment.agent_name, Assignment.domain,
                    Assignment.capabilities, Assignment.superglue_tool_id,
                    Assignment.superglue_tool_status, Assignment.status,
                ).where(
                    Assignment.company_id == company_id,
                    Assignment.superglue_tool_id.isnot(None),
                )
            ).fetchall()
        return [
            {
                "agent_name": r[0], "domain": r[1], "capabilities": r[2],
                "tool_id": r[3], "tool_status": r[4], "agent_status": r[5],
            }
            for r in rows
        ]
    except Exception as e:  # noqa: BLE001
        return [{"error": str(e)[:300]}]


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        os.environ.setdefault("PARWA_DATABASE_URL", "sqlite:////tmp/parwa_registry_smoke.db")
        if os.path.exists("/tmp/parwa_registry_smoke.db"):
            os.remove("/tmp/parwa_registry_smoke.db")
        r = register_tool(
            company_id="smoke-tenant",
            tool_id="tenant_smoke-tenant__meeting-setup",
            tool_name="Meeting Setup / Booking",
            risk="write",
            approval_required=True,
            capability="meeting_setup",
            created_by="self_extension",
            origin="self_extension",
            created_for_ticket="TKT-SMOKE-1",
            tool_definition={"id": "meeting-setup", "steps": 1},
        )
        print("register:", json.dumps(r))
        print("tenant tools:", json.dumps(list_tools_for_tenant("smoke-tenant")))
        print("agent links:", json.dumps(list_agents_with_tools("smoke-tenant")))
        ok = r.get("ok") and r.get("inventory") == "inserted" and r.get("agent_link") == "inserted"
        print("SMOKE:", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    print(__doc__)
