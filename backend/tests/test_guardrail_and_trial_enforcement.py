"""Tests for the 2026-09-19 post-resume-26 fixes:

1. Awareness-guardrail unblock (pipeline_dispatcher._check_tenant_awareness):
   the old "ticket mentions refund/cancel + 0 active tools → review_needed"
   block fired BEFORE the pipeline, so SuperGlue Tool-Forge never got the
   chance to create the tool it exists to create (live finding 2026-09-18/19).
   Now ONLY a truly empty tenant (0 agents AND 0 KB) is blocked.

2. Trial enforcement default flip (ticket_service._check_trial_limit):
   TRIAL_LIMIT_DISABLED defaulted to "true" (production-testing leftover),
   which left the trial counter stuck at 0/15. Per user product decision —
   "trial = paid quality, only 15 tickets" — enforcement is now ON unless
   the env var is EXPLICITLY set to "true".

Run:  cd backend && ../venv/bin/python -m pytest tests/test_guardrail_and_trial_enforcement.py -q
"""

import ast
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DISPATCHER = BACKEND_DIR / "app/services/pipeline_dispatcher.py"
TICKET_SERVICE = BACKEND_DIR / "app/services/ticket_service.py"
VENV_PY = BACKEND_DIR.parent / "venv" / "bin" / "python"


def _ast_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _run_py(code: str, extra_env: dict | None = None, timeout: int = 120) -> str:
    """Run python in a clean subprocess from the backend dir (house style).

    DATABASE_URL is HARD-SET to a UNIQUE fresh sqlite file per run so the
    test can never read or write a foreign database.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///./test_guardrail_{uuid.uuid4().hex[:8]}.db"
    if extra_env:
        env.update(extra_env)
    out = subprocess.run(
        [str(VENV_PY), "-c", code],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if out.returncode != 0:
        raise AssertionError(f"subprocess failed:\n{out.stdout}\n{out.stderr}")
    return out.stdout


# ── 1. guardrail: static source checks ─────────────────────────────────


def test_guardrail_no_longer_blocks_on_missing_tools():
    """The action-keyword block must be GONE from _check_tenant_awareness.

    A ticket is never unsolvable just because tools don't exist YET —
    Node 5 Tool-Forge creates them at execution time.
    """
    src = DISPATCHER.read_text()
    assert "action_keywords" not in src, (
        "old action-keyword list still present — it blocked Tool-Forge "
        "from ever firing (review_needed before the pipeline could create)"
    )
    assert "ticket needs action" not in src, (
        "old blocking reason still present — tickets with 0 tools must "
        "flow through so Tool-Forge can create the tool"
    )


def test_guardrail_still_blocks_truly_empty_tenant():
    """The ONLY can_solve=False path is 0 agents AND 0 KB (onboarding incomplete)."""
    src = DISPATCHER.read_text()
    assert "tenant has 0 agents and 0 KB documents" in src, (
        "empty-tenant guard must stay — nothing to clone or answer from"
    )


def test_guardrail_function_shape_unchanged():
    """_check_tenant_awareness must exist, return the documented dict shape,
    and contain exactly ONE can_solve=False return inside the try block."""
    tree = _ast_tree(DISPATCHER)
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_check_tenant_awareness":
            func = node
            break
    assert func is not None, "_check_tenant_awareness not found"
    src = ast.get_source_segment(DISPATCHER.read_text(), func)
    assert '"can_solve": False' in src
    assert '"can_solve": True' in src
    # Exactly TWO blocking reasons: 'ticket not found' + the empty-tenant one.
    # Any THIRD reason (like the old 'ticket needs action') is a regression.
    assert src.count('"can_solve": False') == 2, (
        "guardrail must have exactly 2 blocking paths (not-found + empty "
        f"tenant), found {src.count('\"can_solve\": False')}"
    )
    assert '0 agents and 0 KB documents' in src
    assert 'ticket not found' in src


# ── 2. guardrail: behavioural test against a REAL sqlite DB ────────────

_GUARDRAIL_SCRIPT = r"""
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models.tickets import Ticket
from database.models.core import Company
from database.models.variant_engine import AIAgentAssignment
from database.models.onboarding import KnowledgeDocument

engine = create_engine("sqlite:///./test_guardrail_bh.db")
for m in (Company, Ticket, AIAgentAssignment, KnowledgeDocument):
    m.__table__.create(engine, checkfirst=True)
maker = sessionmaker(bind=engine)

CO_EMPTY  = "aaaaaaa1-0000-0000-0000-000000000000"  # 0 agents, 0 KB
CO_KBONLY = "aaaaaaa2-0000-0000-0000-000000000000"  # 0 agents, 1 KB doc
CO_NOTOOL = "aaaaaaa3-0000-0000-0000-000000000000"  # 1 agent, 0 tools
CO_FULL   = "aaaaaaa4-0000-0000-0000-000000000000"  # 1 agent + active tool

with maker() as db:
    db.add(Ticket(id="t-empty", company_id=CO_EMPTY, channel="chat",
                  status="open", subject="I want a refund for order 123"))
    db.add(Ticket(id="t-kbonly", company_id=CO_KBONLY, channel="chat",
                  status="open", subject="How do I reset my password?"))
    db.add(KnowledgeDocument(company_id=CO_KBONLY, filename="faq.pdf"))
    db.add(Ticket(id="t-notool", company_id=CO_NOTOOL, channel="chat",
                  status="open", subject="Please cancel my subscription"))
    db.add(AIAgentAssignment(company_id=CO_NOTOOL, agent_name="Refunds Agent",
                             capabilities='["refund_processing"]',
                             superglue_tool_id=None, superglue_tool_status="none"))
    db.add(Ticket(id="t-full", company_id=CO_FULL, channel="chat",
                  status="open", subject="Where is my order?"))
    db.add(AIAgentAssignment(company_id=CO_FULL, agent_name="Orders Agent",
                             capabilities='["shipping_delivery"]',
                             superglue_tool_id="tenant_x__track_order",
                             superglue_tool_status="active"))
    db.commit()

import database.base as dbase
dbase.SessionLocal = maker  # point the dispatcher at sqlite

from app.services.pipeline_dispatcher import _check_tenant_awareness

results = {
    "empty":  _check_tenant_awareness("t-empty",  CO_EMPTY),
    "kbonly": _check_tenant_awareness("t-kbonly", CO_KBONLY),
    "notool": _check_tenant_awareness("t-notool", CO_NOTOOL),
    "full":   _check_tenant_awareness("t-full",   CO_FULL),
    "missing": _check_tenant_awareness("no-such-ticket", CO_FULL),
}
print(json.dumps(results))
"""


def test_guardrail_action_ticket_without_tools_flows_through():
    """THE regression test: refund/cancel ticket + agent with NO tool must be
    ALLOWED so Node 5 Tool-Forge can create the tool. Old code: review_needed."""
    data = json.loads(_run_py(_GUARDRAIL_SCRIPT))
    (BACKEND_DIR / "test_guardrail_bh.db").unlink(missing_ok=True)

    # Truly empty tenant → still blocked (onboarding incomplete)
    assert data["empty"]["can_solve"] is False, "empty tenant must stay blocked"
    assert "0 agents and 0 KB" in data["empty"]["reason"]

    # KB-only tenant → allowed (knowledge tickets are answerable)
    assert data["kbonly"]["can_solve"] is True, (
        f"KB-only tenant blocked: {data['kbonly']['reason']}"
    )

    # THE FIX: action ticket + agent with NO tool → allowed (Tool-Forge creates it)
    assert data["notool"]["can_solve"] is True, (
        f"action ticket with 0 tools still blocked — Tool-Forge can never fire: "
        f"{data['notool']['reason']}"
    )

    # Fully equipped tenant → allowed
    assert data["full"]["can_solve"] is True

    # Missing ticket → blocked (not found)
    assert data["missing"]["can_solve"] is False


# ── 3. trial enforcement: default is now ON ─────────────────────────────

_TRIAL_SCRIPT_TMPL = r"""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models.core import Company

engine = create_engine("sqlite:///./test_trial_bh.db")
Company.__table__.create(engine, checkfirst=True)
maker = sessionmaker(bind=engine)

CO_TRIAL = "bbbbbbb1-0000-0000-0000-000000000000"
CO_PAID  = "bbbbbbb2-0000-0000-0000-000000000000"

with maker() as db:
    db.add(Company(id=CO_TRIAL, name="TrialCo", industry="saas",
                   subscription_tier="trial", is_trial=True,
                   trial_tickets_used={USED},
                   trial_started_at=datetime.now(timezone.utc) - timedelta(hours={AGE_H}),
                   trial_ends_at=datetime.now(timezone.utc) + timedelta(hours={AGE_H})))
    db.add(Company(id=CO_PAID, name="PaidCo", industry="saas",
                   subscription_tier="parwa", is_trial=False,
                   trial_tickets_used=99))
    db.commit()

# Build the service WITHOUT __init__ (avoids the rate-limiter import chain)
from app.services.ticket_service import TicketService

def check(company_id):
    svc = TicketService.__new__(TicketService)
    svc.db = maker()
    svc.company_id = company_id
    try:
        svc._check_trial_limit()
        return "ok"
    except Exception as exc:
        code = getattr(exc, "details", {}).get("reason", "") or type(exc).__name__
        return code

print(json.dumps({
    "trial": check(CO_TRIAL),
    "paid": check(CO_PAID),
}))
"""


def _run_trial(used: int, age_hours: float, extra_env: dict | None = None) -> dict:
    code = (_TRIAL_SCRIPT_TMPL
            .replace("{USED}", str(used))
            .replace("{AGE_H}", str(age_hours)))
    out = _run_py(code, extra_env=extra_env)
    (BACKEND_DIR / "test_trial_bh.db").unlink(missing_ok=True)
    return json.loads(out)


def test_trial_limit_15_enforced_by_default():
    """15/15 used + env unset → AuthorizationError(TRIAL_TICKET_LIMIT).
    This is the user decision: the 15-ticket cap is the ONLY trial limit
    and it must actually count."""
    data = _run_trial(used=15, age_hours=10)
    assert data["trial"] == "TRIAL_TICKET_LIMIT", (
        f"15-ticket cap not enforced by default: got {data['trial']!r}"
    )


def test_trial_under_limit_passes():
    """14/15 used → no raise (counter genuinely counts, blocks only at 15)."""
    data = _run_trial(used=14, age_hours=10)
    assert data["trial"] == "ok", f"14/15 must pass: got {data['trial']!r}"


def test_trial_disabled_is_explicit_optout_only():
    """TRIAL_LIMIT_DISABLED=true (explicit) → checks skipped (escape hatch)."""
    data = _run_trial(used=99, age_hours=48,
                      extra_env={"TRIAL_LIMIT_DISABLED": "true"})
    assert data["trial"] == "ok", "explicit opt-out must skip the check"


def test_paid_company_never_gated():
    """is_trial=False → never blocked, no matter the preserved count."""
    data = _run_trial(used=15, age_hours=10)
    assert data["paid"] == "ok", "paid company must never be trial-gated"


def test_trial_time_expiry_still_enforced():
    """24h window expired (tickets under limit) → TRIAL_TIME_EXPIRED."""
    data = _run_trial(used=3, age_hours=-30)  # ends_at 30h in the past
    assert data["trial"] == "TRIAL_TIME_EXPIRED", (
        f"expired 24h trial not detected: got {data['trial']!r}"
    )


# ── 4. static sanity: ticket_service default flip is in place ───────────

def test_trial_default_flipped_in_source():
    """The env default must be 'false' (enforced) — the old 'true' default
    was the production-testing leftover that kept the counter at 0/15."""
    src = TICKET_SERVICE.read_text()
    assert 'TRIAL_LIMIT_DISABLED", "false"' in src, (
        "TRIAL_LIMIT_DISABLED still defaults to enabled-off — the trial "
        "counter will stay stuck at 0/15"
    )
