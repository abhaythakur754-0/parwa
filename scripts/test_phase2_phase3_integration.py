"""
PHASE 2 + PHASE 3 INTEGRATION TEST — CRM history backfill + auto-retry on connect.

Phase 2 (learning from CRM history):
  P2-1  Batch 1 learns page-1 tickets, persists state + cursor on the CRM row
  P2-2  The AI wiki RECALLS a backfilled pattern (find_similar_patterns) —
        this is the memory the pipeline answers from on the next ticket
  P2-3  Batch 2 (cursor) learns page-2, reports complete
  P2-4  Re-run is IDEMPOTENT — everything deduped by stable content hash
  P2-5  GET /api/integrations/crm-history/status works through the real API
  P2-6  POST /api/integrations/crm-history/backfill runs in background and
        updates state visible through the status endpoint

Phase 3 (auto-retry when the missing connection arrives):
  P3-1  crm_pending + missing_connection(payment) ticket + "stripe" connected
        → ticket requeued to open (state machine reason auto_retry) + dispatch
  P3-2  Non-matching ticket (shipping ask) untouched by a payments connect
  P3-3  Thrash guard: ticket already auto-retried MAX times is skipped
  P3-4  The REAL connect endpoint (POST /api/integrations) fires the sweep —
        connecting Stripe requeues the waiting ticket end-to-end

Run (single command — sandbox reaps background processes between calls):
    /home/z/.venv/bin/python3 scripts/test_phase2_phase3_integration.py
"""

import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = "/tmp/phase23_test.db"
MOCK_PORT = 9098

# Hard set (NOT setdefault): the sandbox shell may export its own DATABASE_URL.
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
# Sandbox proxies must not intercept the localhost mock-CRM calls.
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# ── Embedded Zendesk-style mock CRM (in-process — sandbox kills daemons) ──

Z_TICKETS_PAGE1 = [
    {"id": 501, "subject": "Refund for double charge", "type": "incident",
     "description": "I was charged twice on Friday for order 881.",
     "created_at": "2026-01-01T10:00:00Z"},
    {"id": 502, "subject": "Coupon code rejected at checkout", "type": "question",
     "description": "SAVE20 says invalid but it should work.",
     "created_at": "2026-01-02T10:00:00Z"},
    {"id": 503, "subject": "Wrong size delivered", "type": "incident",
     "description": "Received M instead of the L I ordered.",
     "created_at": "2026-01-03T10:00:00Z"},
]
Z_TICKETS_PAGE2 = [
    {"id": 504, "subject": "Invoice VAT number wrong", "type": "question",
     "description": "Our GST number is missing on the invoice.",
     "created_at": "2026-01-04T10:00:00Z"},
]
Z_COMMENTS = {
    501: [{"body": "I was charged twice on Friday for order 881."},
          {"body": "<p>Refunded the duplicate $49.00 transaction, confirmation sent.</p>"}],
    502: [{"body": "SAVE20 says invalid but it should work."},
          {"body": "Reissued coupon SAVE20-NEW, valid 30 days."}],
    503: [{"body": "Received M instead of the L I ordered."},
          {"body": "Free pickup arranged; correct size ships today."}],
    504: [{"body": "Our GST number is missing on the invoice."},
          {"body": "Reissued invoice with GST 22AAAA0000A1Z5."}],
}


class _MockZendeskHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        params = dict(p.split("=", 1) for p in self.path.split("?")[1].split("&")
                      if "=" in p) if "?" in self.path else {}
        if path.endswith("/tickets.json"):
            page = int(params.get("page", "1"))
            per_page = int(params.get("per_page", "50"))
            all_pages = {1: Z_TICKETS_PAGE1, 2: Z_TICKETS_PAGE2}
            tickets = all_pages.get(page, [])[:per_page]
            body = json.dumps({"tickets": tickets}).encode()
        elif "/comments.json" in path:
            # /api/v2/tickets/{id}/comments.json → id is second-to-last segment
            tid = int(path.split("/")[-2])
            body = json.dumps({"comments": Z_COMMENTS.get(tid, [])}).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


_server = ThreadingHTTPServer(("127.0.0.1", MOCK_PORT), _MockZendeskHandler)
threading.Thread(target=_server.serve_forever, daemon=True).start()
print(f"[mock-zendesk] listening on 127.0.0.1:{MOCK_PORT}")

# Point the Zendesk adapter at the mock BEFORE any fetch happens.
from app.core.crm_bridge.crm_bridge import ZendeskAdapter  # noqa: E402

ZendeskAdapter.API_BASE = f"http://127.0.0.1:{MOCK_PORT}/api/v2"

from database.base import SessionLocal, init_db, get_db  # noqa: E402
from database.models.core import Company  # noqa: E402
from database.models.integration import Integration  # noqa: E402
from database.models.tickets import Ticket  # noqa: E402
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store  # noqa: E402
from app.services.crm_history_backfill import (  # noqa: E402
    get_backfill_state,
    run_backfill_batch,
)
from app.services import pipeline_dispatcher as pd_mod  # noqa: E402
from app.services.auto_retry_service import retry_tickets_for_integration  # noqa: E402
from app.services.escalation_ask import build_escalation_ask  # noqa: E402

init_db()

COMPANY = "33333333-3333-3333-3333-333333333333"

db = SessionLocal()
db.add(Company(id=COMPANY, name="Phase23 Co", industry="ecommerce",
               subscription_tier="parwa", subscription_status="active"))
db.add(Integration(id=str(uuid.uuid4()), company_id=COMPANY,
                   integration_type="zendesk", name="Mock Zendesk",
                   status="active",
                   credentials_encrypted=json.dumps(
                       {"subdomain": "mock", "email": "a@b.c", "api_key": "tok"}),
                   settings="{}"))
db.commit()

PASS, FAIL = "✅ PASS", "❌ FAIL"
_results = {"pass": 0, "fail": 0}


def check(name, cond, detail=""):
    _results["pass" if cond else "fail"] += 1
    print(f"{PASS if cond else FAIL}  {name}" + (f"  — {detail}" if detail else ""))


def make_ticket(ticket_id, status, ask, auto_retry_count=0):
    meta = {"escalation_type": "missing_connection", "escalation_ask": ask}
    if auto_retry_count:
        meta["auto_retry"] = {"count": auto_retry_count, "integration": "x"}
    t = Ticket(id=ticket_id, company_id=COMPANY, subject="Escalated ticket",
               status=status, priority="high", channel="email",
               awaiting_human=False, metadata_json=json.dumps(meta))
    db.add(t)
    db.commit()
    return t


print("\n══════════ PHASE 2 — learn from CRM history ══════════")

# P2-1: first batch — batch_size=3 so the mock's 3-ticket page is FULL → cursor
s1 = run_backfill_batch(db, COMPANY, batch_size=3)
check("P2-1a batch1 learned page1 (3 tickets)",
      s1["status"] == "done" and s1["fetched"] == 3 and s1["learned"] == 3,
      f"status={s1['status']} fetched={s1['fetched']} learned={s1['learned']}")
check("P2-1b has_more + cursor persisted on the CRM row",
      s1["has_more"] is True and
      (get_backfill_state(db, COMPANY)["state"] or {}).get("cursor") == "2")

# P2-2: the wiki recalls the backfilled pattern (the whole point)
patterns = get_wiki_store().find_similar_patterns(
    tenant_id=COMPANY, query="refund for double charge on my order",
    ticket_type="incident", max_results=3)
check("P2-2 wiki recalls backfilled resolution pattern",
      any("Refunded the duplicate $49.00 transaction" in (p.get("answer_summary") or "")
          for p in patterns),
      f"recalled={len(patterns)}")

# P2-3: second batch via cursor → complete (page 2 has 1 ticket < 3 → last page)
s2 = run_backfill_batch(db, COMPANY, batch_size=3)
check("P2-3 batch2 learns page2 + reports complete",
      s2["status"] == "complete" and s2["learned"] == 1 and s2["has_more"] is False)

# P2-4: idempotent re-run (starts over at page 1, all duplicates)
s3 = run_backfill_batch(db, COMPANY, batch_size=50)
check("P2-4 re-run dedupes everything (idempotent)",
      s3["learned"] == 0 and s3["duplicates_skipped"] == 3)

state = get_backfill_state(db, COMPANY)
check("P2-4b cumulative counters correct",
      state["state"]["patterns_learned"] == 4 and state["state"]["batches_done"] == 3,
      f"learned={state['state']['patterns_learned']} batches={state['state']['batches_done']}")

print("\n══════════ PHASE 2 — through the real API ══════════")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


class _FakeUser:
    id = "user-1"
    company_id = COMPANY
    email = "owner@phase23.test"


def _override_get_db():
    yield db


app.dependency_overrides[get_db] = _override_get_db
from app.api.deps import get_current_user  # noqa: E402

app.dependency_overrides[get_current_user] = lambda: _FakeUser()
client = TestClient(app)

r = client.get("/api/integrations/crm-history/status")
st = r.json() if r.status_code == 200 else {}
check("P2-5 GET status endpoint works (real router + auth)",
      r.status_code == 200 and st.get("supported") is True
      and st.get("provider") == "zendesk",
      f"http={r.status_code}")

r = client.post("/api/integrations/crm-history/backfill",
                json={"batch_size": 50})
check("P2-6a POST backfill accepted",
      r.status_code == 200 and r.json().get("status") == "started",
      f"http={r.status_code} body={r.json().get('status')}")

# Background thread runs with its own session — poll until batch 4 lands.
deadline = time.time() + 30
batches = 3
while time.time() < deadline:
    time.sleep(0.5)
    st = client.get("/api/integrations/crm-history/status").json()
    if (st.get("state") or {}).get("batches_done", 0) >= batches + 1:
        break
st_state = st.get("state") or {}
check("P2-6b background batch ran + visible via status",
      st_state.get("batches_done", 0) == batches + 1
      and st_state.get("patterns_learned", 0) == 4,
      f"batches={st_state.get('batches_done')} learned={st_state.get('patterns_learned')}")

print("\n══════════ PHASE 3 — auto-retry on connect ══════════")

T_PAY = "t-pay-0001"
T_SHIP = "t-ship-0002"
T_CAPPED = "t-capped-0003"
make_ticket(T_PAY, "crm_pending", build_escalation_ask("no_tool_for_action", "execute_refund"))
make_ticket(T_SHIP, "crm_pending", build_escalation_ask("no_tool_for_action", "track_shipment"))
make_ticket(T_CAPPED, "crm_pending",
            build_escalation_ask("no_tool_for_action", "execute_refund"), auto_retry_count=3)

# Capture dispatches (the endpoint resolves dispatch at call time → this sticks)
_dispatched = []
_real_dispatch = pd_mod.dispatch_pipeline_for_ticket
pd_mod.dispatch_pipeline_for_ticket = (
    lambda ticket_id, company_id, priority, channel, sync=None:
    _dispatched.append(ticket_id) or {"status": "queued", "ticket_id": ticket_id})

summary = retry_tickets_for_integration(db, COMPANY, "stripe", "payments")

check("P3-1 matching ticket requeued to open + dispatch fired",
      summary["retried"] == 1 and T_PAY in summary["ticket_ids"]
      and _dispatched == [T_PAY],
      f"retried={summary['retried']} dispatched={_dispatched}")
t_pay = db.query(Ticket).filter(Ticket.id == T_PAY).first()
check("P3-1b ticket now open + auto_retry recorded in metadata",
      t_pay.status == "open"
      and json.loads(t_pay.metadata_json)["auto_retry"]["count"] == 1)

t_ship = db.query(Ticket).filter(Ticket.id == T_SHIP).first()
check("P3-2 non-matching (shipping ask) untouched by payments connect",
      t_ship.status == "crm_pending" and T_SHIP not in _dispatched)

check("P3-3 thrash guard: max-retried ticket skipped",
      summary["skipped_max_retries"] == 1
      and db.query(Ticket).filter(Ticket.id == T_CAPPED).first().status == "crm_pending")

# P3-4: the REAL connect endpoint fires the sweep — seed a fresh waiting
# ticket AFTER the sweep above so only the connect event can requeue it.
T_CONNECT = "t-conn-0004"
make_ticket(T_CONNECT, "crm_pending", build_escalation_ask("no_tool_for_action", "execute_refund"))

# The production route must not trigger customer-facing retries for an
# unverified/pending connection. Simulate a successful Stripe credential
# check so this test exercises the verified-connect auto-retry path without
# making a real provider request.
from app.services.integration_service import IntegrationService  # noqa: E402

_original_test_credentials = IntegrationService._test_credentials
IntegrationService._test_credentials = (
    lambda self, integration_type, config:
    {"success": True, "message": "mock credentials verified"}
)
try:
    r = client.post("/api/integrations", json={
        "integration_type": "stripe", "name": "Stripe",
        "config": {"api_key": "sk_test_x"},
        "validate_credentials": True,
    })
finally:
    IntegrationService._test_credentials = _original_test_credentials
check("P3-4a connect endpoint accepted (201)",
      r.status_code == 201, f"http={r.status_code}")
check("P3-4b connect fired auto-retry for the waiting ticket",
      _dispatched.count(T_CONNECT) == 1,
      f"dispatched={_dispatched}")
t_conn = db.query(Ticket).filter(Ticket.id == T_CONNECT).first()
check("P3-4c waiting ticket requeued + retry count recorded",
      t_conn.status == "open"
      and json.loads(t_conn.metadata_json)["auto_retry"]["integration"] == "stripe")

print("\n══════════ RESULT ══════════")
print(f"{_results['pass']} passed, {_results['fail']} failed")
if _results["fail"]:
    sys.exit(1)
print("PHASE 2 + PHASE 3 INTEGRATION: ALL CHECKS PASSED")
