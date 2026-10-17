"""
LOCAL WIRING TEST — "ticket should be same as before we took it from CRM".

Proves the two HumanReplacement CRM fixes in pipeline_dispatcher._push_to_crm_outbound:

  A. CRM-originated ticket (metadata crm_ticket_id, ingested via CRM webhook)
     + AI can't solve → NO duplicate CRM ticket is created. The ORIGINAL CRM
     ticket receives parwa.cannot_resolve (action=reset_to_new) with the
     reason + what the AI tried → CRM team sees the SAME ticket as before,
     visibly marked "AI could not resolve".
     Parwa side: metadata crm_create_status="returned_to_crm", crm_ticket_id
     stays pointing at the original.

  C. Fallback: CRM-originated ticket but the return push FAILS (CRM down)
     → falls through and creates a fresh CRM ticket so the request still
     reaches the team; the pushed internal note says "PARWA AI could not
     resolve ... Reason: ..." — never "auto-resolved".

  D. Channel-originated ticket, AI RESOLVED → note still says
     "auto-resolved by PARWA AI" (honesty works both ways).

Run (mock CRM must be on :9099):
    DATABASE_URL=sqlite:////tmp/crm_wiring_test.db python3 scripts/test_crm_return_wiring.py
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Engine is created at import time in database.base — set URL first.
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/crm_wiring_test.db")
# Sandbox proxies must not intercept the localhost mock-CRM webhook calls.
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)
if os.path.exists("/tmp/crm_wiring_test.db"):
    os.remove("/tmp/crm_wiring_test.db")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# ── Embedded mock CRM (same contract as scripts/mock_crm.py) ────────────
# Started in-process: the sandbox reaps background processes between shell
# commands, so a standalone mock CRM is not reliably alive during the run.
MOCK_LOG = os.environ.get("LOG", "/tmp/mock_crm_wiring_log.jsonl")
GOOD_WEBHOOK = "http://127.0.0.1:9099/webhook"
DEAD_WEBHOOK = "http://127.0.0.1:9999/webhook"  # nothing listens here


class _MockCRMHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            body = {"_raw": raw.decode("utf-8", "replace")[:2000]}
        with open(MOCK_LOG, "a") as fh:
            fh.write(json.dumps(body) + "\n")
        payload = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        return


def start_mock_crm():
    open(MOCK_LOG, "w").close()
    server = ThreadingHTTPServer(("127.0.0.1", 9099), _MockCRMHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


_mock_server = start_mock_crm()
print(f"[mock-crm] listening on 127.0.0.1:9099, log={MOCK_LOG}")

from database.base import SessionLocal, init_db  # noqa: E402
from database.models.core import Company  # noqa: E402
from database.models.integration import Integration  # noqa: E402
from database.models.tickets import Customer, Ticket  # noqa: E402
from app.core.crm_bridge.crm_bridge import CRMBridge  # noqa: E402
from app.services.pipeline_dispatcher import _push_to_crm_outbound  # noqa: E402

init_db()

PASS, FAIL = "✅ PASS", "❌ FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"{PASS if cond else FAIL}  {name}" + (f"  — {detail}" if detail else ""))


def last_mock_events(n=5):
    if not os.path.exists(MOCK_LOG):
        return []
    with open(MOCK_LOG) as fh:
        lines = fh.readlines()[-n:]
    out = []
    for l in lines:
        try:
            d = json.loads(l)
            out.append(d["body"] if isinstance(d, dict) and "body" in d else d)
        except json.JSONDecodeError:
            continue
    return out


def seed(company_id, webhook_url):
    db = SessionLocal()
    db.merge(Company(
        id=company_id, name=f"T {company_id}", industry="saas",
        subscription_tier="parwa", subscription_status="active",
    ))
    db.merge(Customer(
        id=f"cust-{company_id}", company_id=company_id,
        email="c@example.com", name="Test Customer",
    ))
    db.merge(Integration(
        id=f"int-{company_id}", company_id=company_id,
        integration_type="generic", status="active",
        credentials_encrypted=json.dumps({"webhook_url": webhook_url}),
    ))
    db.commit()
    db.close()


def make_ticket(db, ticket_id, company_id, metadata):
    db.merge(Ticket(
        id=ticket_id, company_id=company_id, customer_id=f"cust-{company_id}",
        channel="email", status="crm_pending", subject="Refund not received",
        priority="high", category="billing",
        metadata_json=json.dumps(metadata),
    ))
    db.commit()


def push(db, ticket_id, company_id, status="crm_pending", ai_text="I tried to verify the refund in the payment gateway but could not confirm the settlement status."):
    return _push_to_crm_outbound(
        db=db, ticket_id=ticket_id, company_id=company_id,
        subject="Refund not received",
        description="I was charged twice last week and still have no refund.",
        customer_email="c@example.com", customer_name="Test Customer",
        priority="high", category="billing",
        ai_response_text=ai_text, ai_response_html=f"<p>{ai_text}</p>",
        ticket_status=status, model_used="local-wiring-test",
    )


# ── Test A: CRM-originated → returns to the SAME CRM ticket ─────────────
print("\n── A: CRM-originated escalation returns to ORIGINAL CRM ticket ──")
seed("comp-a", GOOD_WEBHOOK)
db = SessionLocal()
make_ticket(db, "11111111-1111-1111-1111-111111111111", "comp-a", {
    "crm_ticket_id": "CRM-ORIG-77",
    "escalation_reason": "kb_gap_no_tool",
    "crm_provider": "generic",
})
res_a = push(db, "11111111-1111-1111-1111-111111111111", "comp-a")
check("A1 result says returned_to_original", res_a.get("returned_to_original") is True, str(res_a))
check("A2 crm_ticket_id is the ORIGINAL", res_a.get("crm_ticket_id") == "CRM-ORIG-77", str(res_a.get("crm_ticket_id")))

t_a = db.query(Ticket).get("11111111-1111-1111-1111-111111111111")
meta_a = json.loads(t_a.metadata_json)
check("A3 metadata keeps original crm_ticket_id", meta_a.get("crm_ticket_id") == "CRM-ORIG-77", str(meta_a.get("crm_ticket_id")))
check("A4 metadata crm_create_status=returned_to_crm", meta_a.get("crm_create_status") == "returned_to_crm", str(meta_a.get("crm_create_status")))
db.close()

ev = [e for e in last_mock_events(10) if e.get("event") == "parwa.cannot_resolve" and e.get("ticket_id") == "CRM-ORIG-77"]
check("A5 mock CRM got parwa.cannot_resolve for ORIGINAL ticket", len(ev) >= 1)
if ev:
    fc = ev[-1].get("failure_context", {})
    check("A6 payload has action=reset_to_new", ev[-1].get("action") == "reset_to_new", str(ev[-1].get("action")))
    check("A7 reason visible to CRM team", fc.get("failure_analysis") == "kb_gap_no_tool", str(fc.get("failure_analysis")))
    check("A8 what AI tried visible to CRM team", "could not confirm the settlement status" in str(fc.get("what_was_tried", "")))

# ── Test C: return push fails → falls through, honest note on new ticket ─
print("\n── C: return fails → fresh CRM ticket + HONEST 'could not resolve' note ──")
seed("comp-c", DEAD_WEBHOOK)

captured = {}


async def fake_create(**kwargs):
    captured["create"] = kwargs
    return {"success": True, "crm_ticket_id": "CRM-NEW-99", "crm_provider": "generic", "crm_ticket_url": ""}


async def fake_push(**kwargs):
    captured["push"] = kwargs
    return {"success": True, "crm_ticket_id": "CRM-NEW-99", "crm_status": kwargs.get("status")}


_orig_create, _orig_push = CRMBridge.create_ticket, CRMBridge.push_response
CRMBridge.create_ticket = staticmethod(fake_create)
CRMBridge.push_response = staticmethod(fake_push)
try:
    db = SessionLocal()
    make_ticket(db, "33333333-3333-3333-3333-333333333333", "comp-c", {
        "crm_ticket_id": "CRM-ORIG-88",
        "escalation_reason": "response_failed_verification",
    })
    res_c = push(db, "33333333-3333-3333-3333-333333333333", "comp-c")
    db.close()
finally:
    CRMBridge.create_ticket = _orig_create
    CRMBridge.push_response = _orig_push

check("C1 fell through and created fresh CRM ticket", res_c.get("crm_ticket_id") == "CRM-NEW-99", str(res_c))
check("C2 not marked returned_to_original", res_c.get("returned_to_original") is None)
note = str(captured.get("push", {}).get("internal_note", ""))
check("C3 note says AI could NOT resolve", "could not resolve" in note.lower(), note[:120])
check("C4 note includes the reason", "response_failed_verification" in note)
check("C5 note never claims auto-resolved", "auto-resolved" not in note.lower())
check("C6 push status to CRM is escalated", captured.get("push", {}).get("status") == "escalated", str(captured.get("push", {}).get("status")))

# ── Test D: channel-originated RESOLVED → honest success note ────────────
print("\n── D: resolved ticket still reports 'auto-resolved by PARWA AI' ──")
captured.clear()
CRMBridge.create_ticket = staticmethod(fake_create)
CRMBridge.push_response = staticmethod(fake_push)
try:
    db = SessionLocal()
    make_ticket(db, "44444444-4444-4444-4444-444444444444", "comp-c", {})
    res_d = push(db, "44444444-4444-4444-4444-444444444444", "comp-c", status="resolved",
                 ai_text="Your refund of ₹1,200 was processed and will arrive in 3-5 days.")
    db.close()
finally:
    CRMBridge.create_ticket = _orig_create
    CRMBridge.push_response = _orig_push

note_d = str(captured.get("push", {}).get("internal_note", ""))
check("D1 resolved note says auto-resolved by PARWA AI", "auto-resolved by parwa ai" in note_d.lower(), note_d[:120])
check("D2 resolved push status is resolved", captured.get("push", {}).get("status") == "resolved", str(captured.get("push", {}).get("status")))

# ── Summary ──────────────────────────────────────────────────────────────
failed = [r for r in results if not r[1]]
print(f"\n{'=' * 60}\nRESULT: {len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    for name, _, detail in failed:
        print(f"  FAILED: {name} — {detail}")
    sys.exit(1)
print("ALL WIRING CHECKS PASSED — CRM sees the same ticket + honest reason.")
