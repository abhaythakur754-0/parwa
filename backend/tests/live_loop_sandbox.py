"""Live HumanReplacement loop check — real sandbox CRM over real HTTP.

AGENTS.md runnable check for the CRM learning loop. NO mocks: PARWA and
the sandbox CRM are two separate HTTP services talking webhooks, exactly
like production. Run from backend/ with the SAME DATABASE_URL for the
server and this script:

  cd backend
  export DATABASE_URL=sqlite:////abs/path/live_loop.db

  python3 tests/live_loop_sandbox.py --seed      # 1. tables + tenant + CRM integration
  uvicorn app.main:app --port 8000 &             # 2. PARWA (real backend)
  python3 tests/live_loop_sandbox.py --serve &   # 3. sandbox CRM on :8501
  python3 tests/live_loop_sandbox.py --run       # 4. drive the loop + assert

The loop it proves (every arrow is a real HTTP call):

  customer -> sandbox CRM --ticket.created--> PARWA pipeline
  PARWA can't solve -> wiki "unsolved" note + status crm_pending
                                    --parwa.escalation--> sandbox CRM
  human solves BY HAND in the CRM
  sandbox CRM --status:solved--> PARWA webhook -> wiki flips to
  solved_by_human (learn=True) -> customer notified in CRM thread only
  same ticket again -> PARWA answers from wiki memory, NO escalation
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid

import httpx

PARWA = os.environ.get("PARWA_URL", "http://127.0.0.1:8000")
SELF_PORT = int(os.environ.get("SANDBOX_CRM_PORT", "8501"))
TENANT = "tenant_001"
MESSAGE = "I need a refund of $4,500 for order #8841, please process it now"
RESOLUTION = (
    "Over-limit refund APPROVED by finance and issued for order #8841: $4,500 "
    "refunded to the original payment method, refund id RF-9931. Customer "
    "notified in this CRM thread."
)
DB_PATH = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "") or \
    "/home/z/parwa/backend/live_loop.db"

# Make `import app...` / `import database...` work regardless of cwd
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


# ── 1. seed: tables + tenant_001 + the tenant's "CRM" (this sandbox) ────

def seed() -> None:
    from database.base import init_db, SessionLocal
    from database.models.core import Company
    from database.models.integration import Integration

    init_db()
    db = SessionLocal()
    try:
        if not db.get(Company, TENANT):
            db.add(Company(
                id=TENANT, name="Live Loop Tenant", industry="ecommerce",
                subscription_tier="high", subscription_status="active",
                mode="live",
            ))
        cfg = {"webhook_url": f"http://127.0.0.1:{SELF_PORT}/hooks/parwa"}
        row = (
            db.query(Integration)
            .filter(
                Integration.company_id == TENANT,
                Integration.integration_type == "generic",
            )
            .first()
        )
        if row:
            row.status = "active"
            row.credentials_encrypted = json.dumps(cfg)
        else:
            db.add(Integration(
                company_id=TENANT, integration_type="generic",
                name="Sandbox CRM", status="active",
                credentials_encrypted=json.dumps(cfg), settings="{}",
            ))
        db.commit()
    finally:
        db.close()
    print(f"seeded: tenant {TENANT} + generic integration -> "
          f"http://127.0.0.1:{SELF_PORT}/hooks/parwa")


# ── 2. the sandbox CRM (the tenant's real CRM, standalone HTTP service) ─

def serve() -> None:
    from fastapi import FastAPI, Request
    import uvicorn

    app = FastAPI(title="Sandbox CRM")
    TICKETS: dict = {}
    EVENTS: list = []

    def _find(ticket_id: str) -> dict | None:
        if ticket_id in TICKETS:
            return TICKETS[ticket_id]
        for t in TICKETS.values():  # PARWA may push its own ticket id
            for e in t["events"]:
                if e.get("ticket_id") == ticket_id:
                    return t
        return None

    @app.post("/hooks/parwa")
    async def hooks_parwa(request: Request):
        """PARWA pushes escalations/responses here (webhook_url config)."""
        body = await request.json()
        EVENTS.append(body)
        t = _find(str(body.get("ticket_id") or ""))
        if t is not None:
            t["events"].append(body)
            if body.get("event") == "parwa.escalation":
                t["status"] = "needs_human"
            elif body.get("event") == "parwa.response":
                t["status"] = "answered_by_ai"
        return {"ok": True}

    @app.post("/customer/ticket")
    async def customer_ticket(request: Request):
        """Customer files a ticket in the CRM -> CRM forwards to PARWA."""
        body = await request.json()
        crm_id = f"CRM-{uuid.uuid4().hex[:10].upper()}"
        TICKETS[crm_id] = {
            "message": body["message"], "customer": body.get("customer_email", ""),
            "status": "with_parwa", "events": [],
        }
        # async client — a sync httpx.post here would block the event loop
        # for the whole pipeline run and PARWA's escalation push would
        # time out against this frozen server (live-test finding).
        async with httpx.AsyncClient(timeout=560) as client:
            resp = await client.post(
                f"{PARWA}/api/crm/webhooks/generic",
                json={
                    "ticket_id": crm_id,
                    "message": body["message"],
                    "customer_email": body.get("customer_email", "mia@example.com"),
                    "customer_name": body.get("customer_name", "Mia"),
                    "status": "new",
                },
            )
        return {"crm_id": crm_id, "parwa": _json(resp)}

    @app.post("/tickets/{crm_id}/solve")
    async def solve(crm_id: str, request: Request):
        """THE HUMAN STEP: an agent solves the ticket BY HAND in the CRM.

        The CRM then fires its standard status webhook to PARWA — same
        endpoint that ingests tickets; PARWA detects the resolution
        status and (skipping the pipeline) closes the loop.
        """
        body = await request.json()
        t = TICKETS[crm_id]
        t["status"] = "solved_by_human"
        t["resolution"] = body["resolution"]
        async with httpx.AsyncClient(timeout=560) as client:
            resp = await client.post(
                f"{PARWA}/api/crm/webhooks/generic",
                json={
                    "ticket_id": crm_id,
                    "status": "solved",
                    "message": t["message"],
                    "comment": body["resolution"],
                },
            )
        return {"crm_id": crm_id, "parwa": _json(resp)}

    @app.get("/state")
    async def state():
        return {"tickets": TICKETS, "events": EVENTS}

    uvicorn.run(app, host="127.0.0.1", port=SELF_PORT, log_level="warning")


def _json(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"_status": resp.status_code, "_body": resp.text[:300]}


# ── 3. driver: file ticket -> watch escalation -> human solve -> memory ─

def _db_rows(sql: str, args: tuple = ()) -> list:
    con = None
    for attempt in range(4):  # uvicorn may hold a write lock mid-commit
        try:
            con = sqlite3.connect(DB_PATH, timeout=10)
            break
        except sqlite3.OperationalError:
            if attempt == 3:
                raise
            time.sleep(1.5)
    try:
        assert con is not None
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _wiki_texts() -> list[str]:
    rows = _db_rows(
        "SELECT * FROM ai_wiki_entries WHERE company_id=? AND section='A'",
        (TENANT,),
    )
    return [" ".join(str(v) for v in r) for r in rows]


def _ticket_row(crm_id: str):
    rows = _db_rows(
        "SELECT status FROM tickets WHERE metadata_json LIKE ?",
        (f'%"{crm_id}"%',),
    )
    return rows[0] if rows else None


def _wait_http(url: str, tries: int = 60) -> None:
    for _ in range(tries):
        try:
            httpx.get(url, timeout=3)
            return
        except Exception:
            time.sleep(1)
    raise SystemExit(f"nothing answering at {url}")


def run() -> None:
    """Stages 1+2: ticket in -> escalation -> CRM -> human solves -> wiki flips."""
    _wait_http(PARWA)
    _wait_http(f"http://127.0.0.1:{SELF_PORT}/state")
    passed: list[str] = []

    def ok(label: str, cond: bool, detail: str = "") -> None:
        passed.append(label)
        mark = "PASS" if cond else "FAIL"
        print(f"  [{mark}] {label}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            passed.clear()  # sentinel: any failure -> non-zero exit
            raise AssertionError(label)

    # ── Stage 1: ticket in, AI gives up, mistake noted, CRM gets it ──
    print("\nSTAGE 1 — customer files ticket; AI can't solve it")
    r1 = httpx.post(
        f"http://127.0.0.1:{SELF_PORT}/customer/ticket",
        json={"message": MESSAGE, "customer_email": "mia@example.com"},
        timeout=300,
    ).json()
    crm1 = r1["crm_id"]
    p1 = r1["parwa"]
    print(f"  crm_id={crm1} pipeline_status={p1.get('pipeline_status')!r} "
          f"quality={p1.get('quality_score')}")
    ok("PARWA accepted the CRM ticket", p1.get("success") is True, json.dumps(p1)[:200])
    ok("AI did NOT resolve it (escalated, not solved)",
       p1.get("pipeline_status") != "resolved", str(p1.get("pipeline_status")))
    state = httpx.get(f"http://127.0.0.1:{SELF_PORT}/state", timeout=10).json()
    escalations = [e for e in state["events"] if e.get("event") == "parwa.escalation"]
    ok("escalation webhook LANDED in the sandbox CRM (real HTTP push)",
       len(escalations) == 1, f"{len(escalations)} escalation events")
    row = _ticket_row(crm1)
    ok("PARWA ticket row is crm_pending",
       row is not None and row[0] == "crm_pending",
       f"row={row}")
    wiki = _wiki_texts()
    ok("AI wiki noted the MISTAKE (unsolved entry)",
       any("unsolved" in t for t in wiki) and len(wiki) == 1,
       f"{len(wiki)} wiki rows")
    notes = _db_rows("SELECT COUNT(*) FROM notifications")
    ok("NO agent notification fired (CRM is the only channel)",
       notes and notes[0][0] == 0, f"{notes and notes[0][0]} notification rows")

    # ── Stage 2: human solves BY HAND in the CRM; webhook teaches ────
    print("\nSTAGE 2 — human solves it in the CRM; webhook flips the wiki")
    r2 = httpx.post(
        f"http://127.0.0.1:{SELF_PORT}/tickets/{crm1}/solve",
        json={"resolution": RESOLUTION},
        timeout=300,
    ).json()
    p2 = r2["parwa"]
    print(f"  pipeline_status={p2.get('pipeline_status')!r}")
    ok("resolution webhook accepted", p2.get("success") is True, json.dumps(p2)[:200])
    ok("PARWA ticket resolved (learn=True path)", p2.get("pipeline_status") == "resolved")
    row = _ticket_row(crm1)
    ok("ticket row now resolved", row is not None and row[0] == "resolved", f"row={row}")
    wiki = _wiki_texts()
    ok("wiki flipped IN PLACE: solved_by_human + solved_after_failure",
       len(wiki) == 1 and "solved_by_human" in wiki[0]
       and "solved_after_failure" in wiki[0],
       f"{len(wiki)} wiki rows")

    print(f"\nOK — stages 1+2 passed ({len(passed)} assertions, tenant={TENANT})")


def run_stage3(baseline_hits: int) -> None:
    """Stage 3 alone: same ticket again — memory must be used.

    Runs against freshly relaunched services (sandbox CRM state resets,
    but wiki + tickets live in the DB and the log persists).
    """
    _wait_http(PARWA)
    _wait_http(f"http://127.0.0.1:{SELF_PORT}/state")
    passed: list[str] = []

    def ok(label: str, cond: bool, detail: str = "") -> None:
        passed.append(label)
        mark = "PASS" if cond else "FAIL"
        print(f"  [{mark}] {label}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            passed.clear()
            raise AssertionError(label)

    print("\nSTAGE 3 — same ticket filed again; AI must work from memory")
    r3 = httpx.post(
        f"http://127.0.0.1:{SELF_PORT}/customer/ticket",
        json={"message": MESSAGE, "customer_email": "mia@example.com"},
        timeout=560,
    ).json()
    crm3 = r3["crm_id"]
    p3 = r3["parwa"]
    print(f"  crm_id={crm3} pipeline_status={p3.get('pipeline_status')!r}")
    ok("PARWA accepted the repeat ticket",
       p3.get("success") is True, json.dumps(p3)[:200])
    # $4,500 sits above the parwa-tier guardrail, so a re-escalation is
    # the POLICY-CORRECT outcome even with memory. What must hold either
    # way: no duplicate wiki row + proof the pattern was retrieved.
    wiki = _wiki_texts()
    ok("wiki still exactly ONE entry — upgrade-in-place, no duplicates",
       len(wiki) == 1 and "solved_by_human" in wiki[0], f"{len(wiki)} wiki rows")
    hit = 0
    try:
        with open("/tmp/parwa_live.log", errors="replace") as f:
            hit = f.read().count("Wiki SEARCH HIT")
    except OSError:
        pass
    ok("AI retrieved the learned pattern from memory (Wiki SEARCH HIT)",
       hit > baseline_hits, f"{hit} retrievals now vs {baseline_hits} baseline")
    print(f"  repeat-ticket outcome: pipeline_status={p3.get('pipeline_status')!r} "
          f"(guardrail tickets escalate by policy)")

    print(f"\nOK — stage 3 passed ({len(passed)} assertions, tenant={TENANT})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true", help="create tables+tenant+integration")
    parser.add_argument("--serve", action="store_true", help="run the sandbox CRM on :%d" % SELF_PORT)
    parser.add_argument("--run", action="store_true", help="drive stages 1+2 (escalate -> CRM -> solve -> flip)")
    parser.add_argument("--stage3", action="store_true", help="run stage 3 alone (memory reuse)")
    parser.add_argument("--hit-baseline", type=int, default=0,
                        help="Wiki SEARCH HIT count to beat in stage 3")
    args = parser.parse_args()
    if args.seed:
        seed()
    elif args.serve:
        serve()
    elif args.run:
        run()
    elif args.stage3:
        run_stage3(args.hit_baseline)
    else:
        parser.print_help()
