"""Unit tests for Phase 2 CRM-history backfill (app/services/crm_history_backfill.py).

Contract: batches of resolved CRM tickets are distilled into AI-wiki
Section-A patterns (dedupe by stable content hash), job state persists on
the CRM Integration row (restart-safe), unsupported/webhook-only CRMs are
rejected cleanly, and a stuck "running" state older than the staleness
window can never wedge the feature.
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database.base import Base  # noqa: E402
from database.models.core import Company  # noqa: E402
from database.models.integration import Integration  # noqa: E402
from database.models.ai_pipeline import AIWikiEntry  # noqa: E402
from app.core.crm_bridge.crm_bridge import _strip_html  # noqa: E402
from app.core.parwa_pipeline.ai_wiki_store import ticket_pattern_entry_key  # noqa: E402
from app.services import crm_history_backfill as cbf  # noqa: E402


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


COMPANY = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def clear_running_guard():
    cbf._running.pop(COMPANY, None)
    yield
    cbf._running.pop(COMPANY, None)


def _company(db, company_id=COMPANY):
    c = Company(
        id=company_id, name="Backfill Test Co", industry="ecommerce",
        subscription_tier="parwa", subscription_status="active",
    )
    db.add(c)
    db.commit()
    return c


def _crm_integration(db, company_id=COMPANY, provider="zendesk", status="active",
                     settings="{}"):
    row = Integration(
        id=str(uuid.uuid4()), company_id=company_id, integration_type=provider,
        name="Test CRM", status=status, settings=settings,
    )
    db.add(row)
    db.commit()
    return row


class _FakeWikiStore:
    """Write-through stub: records patterns AND persists AIWikiEntry rows so
    the dedupe lookup behaves like the real store."""

    def __init__(self, db):
        self.db = db
        self.written = []

    def write_ticket_pattern(self, tenant_id, ticket_type, query, complexity,
                             techniques_used, quality_score, answer_summary,
                             tier="parwa"):
        key = ticket_pattern_entry_key(ticket_type, query)
        if self.db.query(AIWikiEntry.id).filter(
                AIWikiEntry.company_id == tenant_id,
                AIWikiEntry.section == "A",
                AIWikiEntry.entry_key == key).first():
            return None
        self.db.add(AIWikiEntry(
            id=str(uuid.uuid4()), company_id=tenant_id, section="A",
            entry_key=key, title=f"Pattern: {ticket_type}",
            content=json.dumps({"query_pattern": query[:300],
                                "answer_summary": answer_summary[:500]}),
        ))
        self.db.commit()
        entry = type("Entry", (), {"entry_key": key})()
        self.written.append({
            "tenant_id": tenant_id, "ticket_type": ticket_type, "query": query,
            "answer_summary": answer_summary, "techniques": techniques_used,
            "quality": quality_score, "key": key,
        })
        return entry


@pytest.fixture
def fake_store(db, monkeypatch):
    store = _FakeWikiStore(db)
    monkeypatch.setattr(
        "app.core.parwa_pipeline.ai_wiki_store.get_wiki_store", lambda: store)
    return store


def _patch_fetch(monkeypatch, result):
    import app.core.crm_bridge.crm_bridge as bridge

    async def fake_fetch(provider, limit=50, cursor=None, config=None):
        assert limit >= 1
        return dict(result)

    monkeypatch.setattr(bridge.CRMBridge, "fetch_resolved_tickets",
                        staticmethod(fake_fetch))


def _patch_creds(monkeypatch, config=None):
    from app.services.integration_service import IntegrationService

    monkeypatch.setattr(
        IntegrationService, "get_credential_config",
        lambda self, cid, itype: config if config is not None else {"subdomain": "x"},
    )


# ── _strip_html (CRM bodies → wiki-safe text) ────────────────────────────

def test_strip_html_drops_tags_and_entities():
    raw = "<p>Refund&nbsp;processed &amp; settled</p><br>Done"
    assert _strip_html(raw) == "Refund processed & settled Done"


def test_strip_html_collapses_whitespace():
    assert _strip_html("a\n\n  b   c") == "a b c"


def test_strip_html_empty():
    assert _strip_html("") == ""


# ── ticket_pattern_entry_key: deterministic + legacy-compatible ─────────

def test_entry_key_deterministic():
    q = "Refund not received for order 123"
    assert ticket_pattern_entry_key("general", q) == ticket_pattern_entry_key("general", q)


def test_entry_key_matches_legacy_inline_scheme():
    import hashlib

    q = "Customer wants refund for double charge"
    key_terms = " ".join(w for w in q.lower().split() if len(w) > 4)[:60]
    expected = f"general_{hashlib.md5(key_terms.encode()).hexdigest()[:8]}"
    assert ticket_pattern_entry_key("general", q) == expected


def test_entry_key_differs_for_different_questions():
    a = ticket_pattern_entry_key("general", "refund for double charge")
    b = ticket_pattern_entry_key("general", "where is my shipment")
    assert a != b


# ── state persistence on the Integration row ────────────────────────────

def test_write_and_read_state_roundtrip(db):
    _company(db)
    row = _crm_integration(db, settings='{"other_key": 7}')
    cbf._write_state(db, row, {"status": "done", "patterns_learned": 5})
    state = cbf._read_state(cbf._find_crm_integration(db, COMPANY)[1])
    assert state["status"] == "done"
    assert state["patterns_learned"] == 5
    # Non-backfill settings keys survive the merge
    import json as _json
    settings = _json.loads(cbf._find_crm_integration(db, COMPANY)[1].settings)
    assert settings["other_key"] == 7


def test_read_state_survives_corrupted_settings(db):
    _company(db)
    row = _crm_integration(db, settings="{broken json")
    assert cbf._read_state(row) == {}


def test_merge_state_keeps_old_counters():
    old = {"status": "done", "patterns_learned": 10, "cursor": "3"}
    merged = cbf._merge_state(old, {"status": "complete", "cursor": None})
    assert merged["patterns_learned"] == 10
    assert merged["status"] == "complete"
    assert merged["cursor"] is None


# ── get_backfill_state: support matrix ──────────────────────────────────

def test_state_no_crm_integration(db):
    _company(db)
    result = cbf.get_backfill_state(db, COMPANY)
    assert result["supported"] is False
    assert result["reason"] == "no_crm_integration"


def test_state_generic_crm_unsupported(db):
    _company(db)
    _crm_integration(db, provider="generic")
    result = cbf.get_backfill_state(db, COMPANY)
    assert result["supported"] is False
    assert result["reason"] == "webhook_only_crm_no_read_api"


def test_state_zendesk_supported(db):
    _company(db)
    _crm_integration(db, provider="zendesk")
    result = cbf.get_backfill_state(db, COMPANY)
    assert result["supported"] is True
    assert result["provider"] == "zendesk"
    assert result["state"] == {}  # never run


# ── run_backfill_batch: the whole flow ──────────────────────────────────

_TICKETS = [
    {"crm_ticket_id": "Z1", "subject": "Refund for double charge",
     "description": "I was charged twice on Friday.",
     "resolution_text": "Refunded the duplicate $49 transaction.",
     "ticket_type": "incident", "created_at": "2026-01-01"},
    {"crm_ticket_id": "Z2", "subject": "Where is my shipment",
     "description": "Order 777 not arrived.",
     "resolution_text": "Reshipped via express, tracking sent.",
     "ticket_type": "question", "created_at": "2026-01-02"},
]


def test_batch_learns_and_persists_state(db, fake_store, monkeypatch):
    _company(db)
    _crm_integration(db)
    _patch_fetch(monkeypatch, {"success": True, "supported": True,
                               "tickets": _TICKETS,
                               "next_cursor": "2", "error": None})
    _patch_creds(monkeypatch)

    summary = cbf.run_backfill_batch(db, COMPANY, batch_size=50)
    assert summary["status"] == "done"
    assert summary["fetched"] == 2
    assert summary["learned"] == 2
    assert summary["has_more"] is True

    # State persisted on the integration row
    row = cbf._find_crm_integration(db, COMPANY)[1]
    state = cbf._read_state(row)
    assert state["status"] == "done"
    assert state["cursor"] == "2"
    assert state["batches_done"] == 1
    assert state["patterns_learned"] == 2

    # Distillation content sanity
    w = fake_store.written[0]
    assert "Refund for double charge" in w["query"]
    assert w["answer_summary"] == "Refunded the duplicate $49 transaction."
    assert w["techniques"] == ["CRM_History_Backfill", "CRM_Learning"]


def test_batch_final_page_reports_complete(db, fake_store, monkeypatch):
    _company(db)
    _crm_integration(db)
    _patch_fetch(monkeypatch, {"success": True, "supported": True,
                               "tickets": _TICKETS[:1],
                               "next_cursor": None, "error": None})
    _patch_creds(monkeypatch)
    summary = cbf.run_backfill_batch(db, COMPANY)
    assert summary["status"] == "complete"
    assert summary["has_more"] is False
    state = cbf._read_state(cbf._find_crm_integration(db, COMPANY)[1])
    assert state["status"] == "complete"
    assert state["cursor"] is None


def test_batch_dedupes_on_rerun(db, fake_store, monkeypatch):
    _company(db)
    _crm_integration(db)
    _patch_fetch(monkeypatch, {"success": True, "supported": True,
                               "tickets": _TICKETS,
                               "next_cursor": None, "error": None})
    _patch_creds(monkeypatch)
    cbf.run_backfill_batch(db, COMPANY)
    summary2 = cbf.run_backfill_batch(db, COMPANY)
    assert summary2["learned"] == 0
    assert summary2["duplicates_skipped"] == 2
    assert len(fake_store.written) == 2  # nothing written twice


def test_batch_skips_empty_records(db, fake_store, monkeypatch):
    _company(db)
    _crm_integration(db)
    _patch_fetch(monkeypatch, {"success": True, "supported": True,
                               "tickets": [{"crm_ticket_id": "Z3", "subject": "",
                                            "description": "", "resolution_text": "",
                                            "ticket_type": "general", "created_at": ""},
                                           {"crm_ticket_id": "", "subject": "no id",
                                            "description": "x", "resolution_text": "",
                                            "ticket_type": "general", "created_at": ""}],
                               "next_cursor": None, "error": None})
    _patch_creds(monkeypatch)
    summary = cbf.run_backfill_batch(db, COMPANY)
    assert summary["learned"] == 0
    assert summary["duplicates_skipped"] == 2


def test_batch_fetch_error_persists_error_state(db, fake_store, monkeypatch):
    _company(db)
    _crm_integration(db)
    _patch_fetch(monkeypatch, {"success": False, "supported": True, "tickets": [],
                               "next_cursor": None, "error": "zendesk_list_http_503"})
    _patch_creds(monkeypatch)
    summary = cbf.run_backfill_batch(db, COMPANY)
    assert summary["status"] == "error"
    state = cbf._read_state(cbf._find_crm_integration(db, COMPANY)[1])
    assert state["status"] == "error"
    assert "503" in state["error"]


def test_batch_without_crm_is_a_clean_noop(db):
    _company(db)
    summary = cbf.run_backfill_batch(db, COMPANY)
    assert summary["status"] == "no_crm_integration"


def test_batch_generic_crm_unsupported(db, fake_store):
    _company(db)
    _crm_integration(db, provider="generic")
    summary = cbf.run_backfill_batch(db, COMPANY)
    assert summary["status"] == "unsupported"
    assert "webhook-only" in summary["error"]


def test_concurrent_run_guard_blocks_second_call(db, fake_store, monkeypatch):
    _company(db)
    _crm_integration(db)
    cbf._running[COMPANY] = time.time()  # simulate a run in flight
    summary = cbf.run_backfill_batch(db, COMPANY)
    assert summary["status"] == "already_running"


def test_stale_running_state_recovers(db, fake_store, monkeypatch):
    """A crashed job (status=running, 20 min old) must not wedge the feature."""
    _company(db)
    stale = {"status": "running",
             "last_run_at": (datetime.now(timezone.utc)
                             - timedelta(minutes=20)).isoformat()}
    _crm_integration(db, settings=json.dumps({cbf.STATE_KEY: stale}))
    _patch_fetch(monkeypatch, {"success": True, "supported": True,
                               "tickets": _TICKETS[:1],
                               "next_cursor": None, "error": None})
    _patch_creds(monkeypatch)
    summary = cbf.run_backfill_batch(db, COMPANY)
    assert summary["learned"] == 1  # stale state ignored, batch ran


def test_batch_size_clamped_to_100(db, fake_store, monkeypatch):
    _company(db)
    _crm_integration(db)
    seen = {}

    import app.core.crm_bridge.crm_bridge as bridge

    async def fake_fetch(provider, limit=50, cursor=None, config=None):
        seen["limit"] = limit
        return {"success": True, "supported": True, "tickets": [],
                "next_cursor": None, "error": None}

    monkeypatch.setattr(bridge.CRMBridge, "fetch_resolved_tickets",
                        staticmethod(fake_fetch))
    _patch_creds(monkeypatch)
    cbf.run_backfill_batch(db, COMPANY, batch_size=9999)
    assert seen["limit"] == 100
