"""
Live-bug regression tests (2026-09-18, parwa.buzz).

Covers the two backend bugs found while manually testing ticket solving
on the live site:

  1. DUPLICATE AI MESSAGE — one ticket ended up with two identical "ai"
     messages 3s apart. Root cause: the pipeline dispatches the final
     response through ChannelDispatcher TWICE (Node 6.5 inside the graph,
     then the dispatcher's finalize dispatch). _persist_ai_response had
     an idempotency guard but the second dispatch() call did not.
     FIX: content-based idempotency guard inside ChannelDispatcher.dispatch().
     Tests:
       a. identical re-dispatch → no second row, deduplicated=True
       b. DIFFERENT follow-up content → still stored (guard must not
          swallow legitimate new messages)

  2. USAGE COUNTER STUCK AT 0 — /api/billing/usage summed UsageRecord
     rows that only a daily Celery Beat task writes (and it counts
     YESTERDAY). On free Render there is no Celery worker, so the
     dashboard showed "0 / 15 used" forever.
     FIX: get_usage_info() also counts the real tickets table for the
     month and uses the higher of the two numbers.
     Tests:
       c. stale UsageRecord=0 + 3 real tickets → tickets_used=3
       d. aggregated UsageRecord=7 + 1 real ticket → tickets_used=7
          (live count must never LOWER a correct aggregated number)

Run: cd backend && ../venv/bin/python -m pytest tests/test_bugfixes_live.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_py(code: str) -> str:
    env = dict(os.environ)
    env.setdefault("DATABASE_URL", "sqlite:///./test_bugfixes_tmp.db")
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR), env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, f"subprocess failed:\n{out.stderr[-1200:]}"
    return out.stdout.strip().splitlines()[-1]


# ── 1: ChannelDispatcher duplicate-delivery guard ────────────────────────

_DEDUPE_SCRIPT = r'''
import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models.tickets import Ticket, TicketMessage

engine = create_engine("sqlite:///./test_dedupe_tmp.db")
Ticket.__table__.create(engine, checkfirst=True)
TicketMessage.__table__.create(engine, checkfirst=True)
maker = sessionmaker(bind=engine)

from app.core.channel_dispatcher import ChannelDispatcher

with maker() as db:
    db.add(Ticket(id="tk-1", company_id="co-1", channel="chat",
                  status="processing", priority="medium",
                  subject="dup test",
                  created_at=datetime(2026, 9, 18, 6, 0, 0),
                  updated_at=datetime(2026, 9, 18, 6, 0, 0)))
    db.commit()

TEXT = "Hello! I am the AI answer."

# 1st delivery — as Node 6.5 does inside the graph.
with maker() as db:
    r1 = ChannelDispatcher(db).dispatch(
        company_id="co-1", ticket_id="tk-1",
        ai_response_html="<p>x</p>", ai_response_text=TEXT,
        role="ai", model_used="parwa")

# 2nd delivery with the SAME text — as the dispatcher finalize does.
with maker() as db:
    r2 = ChannelDispatcher(db).dispatch(
        company_id="co-1", ticket_id="tk-1",
        ai_response_html="<p>x</p>", ai_response_text=TEXT,
        role="ai", model_used="parwa")

# 3rd delivery with DIFFERENT text — a legitimate follow-up, must store.
with maker() as db:
    r3 = ChannelDispatcher(db).dispatch(
        company_id="co-1", ticket_id="tk-1",
        ai_response_html="<p>y</p>", ai_response_text="Different follow-up",
        role="ai", model_used="parwa")
    n_ai = db.query(TicketMessage).filter_by(ticket_id="tk-1", role="ai").count()

print(json.dumps({
    "r1_status": r1.get("status"), "r1_dedup": bool(r1.get("deduplicated")),
    "r2_status": r2.get("status"), "r2_dedup": bool(r2.get("deduplicated")),
    "r2_same_msg": r2.get("message_id") == r1.get("message_id"),
    "r3_status": r3.get("status"), "r3_dedup": bool(r3.get("deduplicated")),
    "n_ai": n_ai,
}))
'''


def test_duplicate_ai_delivery_is_deduplicated():
    data = json.loads(_run_py(_DEDUPE_SCRIPT))
    (BACKEND_DIR / "test_dedupe_tmp.db").unlink(missing_ok=True)

    assert data["r1_status"] == "sent" and not data["r1_dedup"]
    # Same content twice → deduplicated, points at the existing message.
    assert data["r2_status"] == "sent" and data["r2_dedup"]
    assert data["r2_same_msg"], "2nd dispatch must return the 1st message id"
    # Different content is a legitimate follow-up — must be stored.
    assert data["r3_status"] == "sent" and not data["r3_dedup"]
    assert data["n_ai"] == 2, f"expected 2 AI messages, got {data['n_ai']}"


# ── 2: usage counter live fallback ───────────────────────────────────────

_USAGE_SCRIPT = r'''
import asyncio, json, uuid
from datetime import date, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models.tickets import Ticket
from database.models.billing import Subscription
from database.models.billing_extended import UsageRecord

engine = create_engine("sqlite:///./test_usage_tmp.db")
Ticket.__table__.create(engine, checkfirst=True)
Subscription.__table__.create(engine, checkfirst=True)
UsageRecord.__table__.create(engine, checkfirst=True)
maker = sessionmaker(bind=engine)

today = date.today()
month = today.strftime("%Y-%m")
CO_LIVE = "11111111-1111-1111-1111-111111111111"   # aggregation stale (0), tickets real (3)
CO_AGG  = "22222222-2222-2222-2222-222222222222"   # aggregation correct (7), tickets real (1)

with maker() as db:
    db.add(Subscription(id="s-1", company_id=CO_LIVE, tier="parwa", status="active"))
    db.add(Subscription(id="s-2", company_id=CO_AGG, tier="parwa", status="active"))
    db.add(UsageRecord(company_id=CO_LIVE, record_date=today, record_month=month, tickets_used=0))
    db.add(UsageRecord(company_id=CO_AGG, record_date=today, record_month=month, tickets_used=7))
    for i in range(3):
        db.add(Ticket(id=f"ut-live-{i}", company_id=CO_LIVE, channel="chat",
                      status="resolved", priority="medium", subject=f"t{i}",
                      created_at=datetime.now(timezone.utc),
                      updated_at=datetime.now(timezone.utc)))
    db.add(Ticket(id="ut-agg-0", company_id=CO_AGG, channel="chat",
                  status="resolved", priority="medium", subject="a",
                  created_at=datetime.now(timezone.utc),
                  updated_at=datetime.now(timezone.utc)))
    db.commit()

import app.services.overage_service as osvc
osvc.SessionLocal = maker  # point the service at sqlite

svc = osvc.OverageService()
live = asyncio.run(svc.get_usage_info(company_id=uuid.UUID(CO_LIVE)))
agg = asyncio.run(svc.get_usage_info(company_id=uuid.UUID(CO_AGG)))

print(json.dumps({
    "live_tickets_used": live.tickets_used,
    "agg_tickets_used": agg.tickets_used,
}))
'''


def test_usage_counter_counts_real_tickets():
    data = json.loads(_run_py(_USAGE_SCRIPT))
    (BACKEND_DIR / "test_usage_tmp.db").unlink(missing_ok=True)

    # Stale aggregation (0) + 3 real tickets → the live count must win.
    assert data["live_tickets_used"] == 3, (
        f"expected live count 3, got {data['live_tickets_used']}"
    )
    # Correct aggregation (7) + 1 ticket → max() must keep 7.
    assert data["agg_tickets_used"] == 7, (
        f"expected aggregated 7, got {data['agg_tickets_used']}"
    )


# ── 3: static sanity — the dispatcher cannot silently lose the guard ─────

def test_dispatch_guard_present_in_source():
    src = (BACKEND_DIR / "app" / "core" / "channel_dispatcher.py").read_text()
    assert "deduplicated" in src
    assert 'TicketMessage.role == "ai"' in src
