"""Unit tests for Phase 3 auto-retry (app/services/auto_retry_service.py).

Contract: when an integration is connected, crm_pending tickets whose
structured escalation ask (escalation_type=missing_connection + capability)
match that integration are transitioned crm_pending → open (reason
auto_retry) and requeued into the worker pool — at most
MAX_TICKETS_PER_EVENT per sweep, MAX_AUTO_RETRIES per ticket, and a
non-matching integration touches nothing.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database.base import Base  # noqa: E402
from database.models.tickets import Ticket  # noqa: E402
from app.services import auto_retry_service  # noqa: E402
from app.services.auto_retry_service import (  # noqa: E402
    MAX_AUTO_RETRIES,
    _ask_matches,
    _auto_retry_count,
    _extract_ask,
    retry_tickets_for_integration,
)
from app.services.escalation_ask import build_escalation_ask  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine):
    Session = sessionmaker(bind=db_engine)
    s = Session()
    yield s
    s.close()


COMPANY = "11111111-1111-1111-1111-111111111111"


def _payment_ask() -> dict:
    return build_escalation_ask("no_tool_for_action", "execute_refund")


def _shipping_ask() -> dict:
    return build_escalation_ask("no_tool_for_action", "track_shipment")


def _make_ticket(db, status="crm_pending", ask=None, auto_retry_count=0,
                 ticket_id=None) -> Ticket:
    meta: dict = {"escalation_type": "missing_connection",
                  "escalation_ask": ask or _payment_ask()}
    if auto_retry_count:
        meta["auto_retry"] = {"count": auto_retry_count, "integration": "x"}
    t = Ticket(
        id=ticket_id or str(uuid.uuid4()),
        company_id=COMPANY,
        subject="Refund not received",
        status=status,
        priority="high",
        channel="email",
        awaiting_human=False,
        metadata_json=json.dumps(meta),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def captured(monkeypatch):
    """Capture dispatch_pipeline_for_ticket calls."""
    calls = []

    def fake_dispatch(ticket_id, company_id, priority, channel, sync=None):
        calls.append({"ticket_id": ticket_id, "company_id": company_id,
                      "priority": priority, "channel": channel, "sync": sync})
        return {"status": "queued", "ticket_id": ticket_id}

    import app.services.pipeline_dispatcher as pd
    monkeypatch.setattr(pd, "dispatch_pipeline_for_ticket", fake_dispatch)
    return calls


# ── _ask_matches: category keywords + provider-name matching ────────────

def test_payment_keywords_match_payment_gateway_ask():
    assert _ask_matches(_payment_ask(), ("payment gateway", "billing integration"), "")


def test_payment_keywords_do_not_match_shipping_ask():
    assert not _ask_matches(_shipping_ask(), ("payment gateway", "billing integration"), "")


def test_provider_name_match_beats_unknown_category():
    # Unmapped category but the connected provider is named in the ask text.
    ask = _shipping_ask()  # examples mention Shippo, ShipStation, AfterShip
    assert _ask_matches(ask, (), "shippo")
    assert not _ask_matches(ask, (), "razorpay")


def test_empty_ask_never_matches():
    assert not _ask_matches({}, ("payment gateway",), "razorpay")


# ── _extract_ask / _auto_retry_count: metadata robustness ───────────────

def test_extract_ask_reads_valid_metadata(db):
    t = _make_ticket(db)
    ask = _extract_ask(t)
    assert ask is not None
    assert ask["escalation_type"] == "missing_connection"


def test_extract_ask_rejects_wrong_escalation_type(db):
    t = _make_ticket(db)
    meta = json.loads(t.metadata_json)
    meta["escalation_type"] = "missing_knowledge"
    t.metadata_json = json.dumps(meta)
    db.commit()
    assert _extract_ask(t) is None


def test_extract_ask_survives_corrupted_metadata(db):
    t = _make_ticket(db)
    t.metadata_json = "{not json at all"
    db.commit()
    assert _extract_ask(t) is None
    assert _auto_retry_count(t) == 0


# ── State machine: the auto_retry transition ─────────────────────────────

def test_state_machine_allows_crm_pending_to_open_auto_retry(db):
    from app.services.ticket_state_machine import TicketStateMachine, TicketStatus

    t = _make_ticket(db)
    TicketStateMachine(db, COMPANY).transition(
        t, to_status=TicketStatus.open, reason="auto_retry")
    assert t.status == "open"


def test_state_machine_rejects_bogus_reason(db):
    from app.services.ticket_state_machine import TicketStateMachine, TicketStatus

    t = _make_ticket(db)
    with pytest.raises(Exception):
        TicketStateMachine(db, COMPANY).transition(
            t, to_status=TicketStatus.open, reason="crm_resolved")


def test_state_machine_still_allows_resolution(db):
    from app.services.ticket_state_machine import TicketStateMachine, TicketStatus

    t = _make_ticket(db)
    TicketStateMachine(db, COMPANY).transition(
        t, to_status=TicketStatus.resolved, reason="crm_resolved")
    assert t.status == "resolved"


# ── retry_tickets_for_integration: the sweep ────────────────────────────

def test_matching_integration_requeues_only_matching_tickets(db, captured):
    match = _make_ticket(db)                        # payment ask, crm_pending
    other = _make_ticket(db, ask=_shipping_ask())   # shipping ask, crm_pending
    wrong_status = _make_ticket(db, status="resolved")

    summary = retry_tickets_for_integration(
        db, COMPANY, "razorpay", category="payments")

    assert summary["retried"] == 1
    assert summary["ticket_ids"] == [str(match.id)]
    db.refresh(match)
    assert match.status == "open"
    meta = json.loads(match.metadata_json)
    assert meta["auto_retry"]["count"] == 1
    assert meta["auto_retry"]["integration"] == "razorpay"

    db.refresh(other)
    assert other.status == "crm_pending"           # untouched
    assert wrong_status.status == "resolved"       # untouched

    assert len(captured) == 1
    assert captured[0]["ticket_id"] == str(match.id)
    assert captured[0]["sync"] is True


def test_provider_name_only_match(db, captured):
    # Unmapped category ("analytics") but the connected provider key is
    # named verbatim in the ask's examples list ("Shippo, ShipStation…").
    t = _make_ticket(db, ask=_shipping_ask())
    db.commit()

    summary = retry_tickets_for_integration(
        db, COMPANY, "shippo", category="analytics")
    assert summary["retried"] == 1
    assert t.status == "open"


def test_max_retries_cap_skips_ticket(db, captured):
    _make_ticket(db, auto_retry_count=MAX_AUTO_RETRIES)
    summary = retry_tickets_for_integration(db, COMPANY, "razorpay", "payments")
    assert summary["retried"] == 0
    assert summary["skipped_max_retries"] == 1
    assert captured == []


def test_no_matching_tickets_is_a_clean_noop(db, captured):
    summary = retry_tickets_for_integration(db, COMPANY, "unknown_tool", "dev_tools")
    assert summary["retried"] == 0
    assert summary["error"] is None
    assert captured == []


def test_auto_retry_count_roundtrip(db):
    t = _make_ticket(db, auto_retry_count=2)
    assert _auto_retry_count(t) == 2
    t2 = _make_ticket(db)
    assert _auto_retry_count(t2) == 0
