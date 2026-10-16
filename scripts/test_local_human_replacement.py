"""
LOCAL E2E test: prove the awaiting_human removal (HumanReplacement) works
through the real API surface of a locally running backend.

Prerequisite:
    DATABASE_URL=sqlite:////home/z/my-project/backend/local_test.db \
        python3 -m uvicorn app.main:app --port 10000   # from backend/
    python3 scripts/mock_crm.py                        # mock CRM :9099

What it proves (pass/fail printed per check):
  1. Register + login works locally.
  2. A generic CRM integration can be attached (webhook_url -> mock CRM).
  3. Ticket creation via POST /api/v1/tickets works.
  4. open/processing -> crm_pending transition (crm_escalation) is legal.
  5. ANY transition INTO awaiting_human is rejected (nothing may enter it).
  6. crm_pending -> resolved (crm_resolved) is legal and sticks.
  7. Status filters: ?status=awaiting_human returns no NEW tickets;
     ?status=crm_pending returns the escalated one before resolution.
  8. The mock CRM received the escalation push (if the pipeline reached
     the escalation branch locally — no LLM keys, so this is best-effort
     and reported as INFO, not FAIL).

Usage:
    BACKEND=http://localhost:10000 python3 scripts/test_local_human_replacement.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BACKEND = os.environ.get("BACKEND", "http://localhost:10000")
MOCK_LOG = os.environ.get("MOCK_LOG", "/home/z/my-project/.mock_crm_log.jsonl")
RUN = str(int(time.time()))

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"   {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def info(name, detail):
    results.append((name, None, detail))
    print(f"   INFO  {name}  — {detail}")


def call(method, path, body=None, token=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BACKEND + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Origin", "http://localhost:3000")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, {}


def mock_crm_hits():
    try:
        with open(MOCK_LOG) as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except FileNotFoundError:
        return []


def _extract_token(payload: dict) -> str:
    """AuthResponse shape: {user, tokens: {access_token, ...}}; be liberal."""
    if not isinstance(payload, dict):
        return ""
    toks = payload.get("tokens") or {}
    return (payload.get("access_token") or payload.get("token")
            or toks.get("access_token") or toks.get("token") or "")


def main() -> int:
    email = f"hr-e2e-{RUN}@localtest.parwa"
    password = "Localtest#2026x"

    print("── 1. register + login ──")
    s, reg = call("POST", "/api/auth/register", {
        "email": email, "password": password, "confirm_password": password,
        "full_name": "HR E2E Tester", "company_name": f"HR E2E {RUN}",
        "industry": "ecommerce",
    })
    check("register 201", s == 201, f"http={s} {str(reg)[:120]}")
    token = _extract_token(reg)
    if not token:
        s, login = call("POST", "/api/auth/login",
                        {"email": email, "password": password})
        token = _extract_token(login)
        check("login fallback", bool(token), f"http={s}")
    check("have JWT", bool(token))
    if not token:
        return 1

    print("── 2. attach generic CRM integration (webhook -> mock CRM) ──")
    # NOTE: 'generic' is a dispatcher-supported provider but not a UI catalog
    # key, so the API rejects it (422). Local test fixture: insert the row
    # the same way a synced integration would exist (plain-JSON creds —
    # exactly what get_credential_config parses).
    import sqlite3
    import uuid as _uuid
    db_path = os.environ.get("LOCAL_DB", "/home/z/my-project/backend/local_test.db")
    con = sqlite3.connect(db_path)
    company_id = ((reg or {}).get("user") or {}).get("company_id") or ""
    if not company_id:  # UserResponse may not carry company_id — look it up
        row = con.execute("SELECT id FROM companies WHERE name = ?",
                          (f"HR E2E {RUN}",)).fetchone()
        company_id = row[0] if row else ""
    con.execute(
        "INSERT INTO integrations (id, company_id, integration_type, name, "
        "status, credentials_encrypted, settings, created_at, updated_at) "
        "VALUES (?, ?, 'generic', 'Local Mock CRM', 'active', "
        "'{\"webhook_url\": \"http://localhost:9099/crm/hook\"}', '{}', "
        "datetime('now'), datetime('now'))",
        (str(_uuid.uuid4()), company_id),
    )
    con.commit()
    con.close()
    check("generic integration row inserted", bool(company_id),
          f"company={company_id[:8]}")

    print("── 3. create ticket (real API, real dispatch) ──")
    s, t = call("POST", "/api/v1/tickets", {
        "subject": "[E2E] Refund stuck — escalate to CRM",
        "description": "Customer was double-charged order #E2E-771 and wants "
                       "a refund. The AI cannot issue refunds over the local "
                       "test environment, so this must escalate to the CRM.",
        "customer_name": "E2E Customer",
        "customer_email": f"customer-{RUN}@localtest.parwa",
        "channel": "email",
    }, token)
    tid = (t or {}).get("id") or (t or {}).get("ticket", {}).get("id")
    check("ticket created", s in (200, 201) and bool(tid), f"http={s} id={tid}")
    if not tid:
        print("   body:", json.dumps(t)[:400])
        return 1

    print("── 4. poll status while the dispatcher settles ──")
    seen = []
    for _ in range(6):
        time.sleep(2)
        _, cur = call("GET", f"/api/v1/tickets/{tid}", token=token)
        st = (cur or {}).get("status")
        if st and (not seen or seen[-1] != st):
            seen.append(st)
    info("status transitions observed", " -> ".join(seen) or "(none)")

    print("── 5. legal transition: -> crm_pending ──")
    s, r = call("PATCH", f"/api/v1/tickets/{tid}/status",
                {"status": "crm_pending", "reason": "crm_escalation"}, token)
    check("crm_pending accepted", s == 200 and r.get("new_status") == "crm_pending",
          f"http={s} {str(r)[:120]}")

    print("── 6. illegal transition: -> awaiting_human must be REJECTED ──")
    s, r = call("PATCH", f"/api/v1/tickets/{tid}/status",
                {"status": "awaiting_human", "reason": "human_replacement"}, token)
    check("awaiting_human rejected", s in (400, 422), f"http={s} {str(r)[:160]}")

    print("── 7. filters ──")
    _, ah = call("GET", "/api/v1/tickets?status=awaiting_human&page=1&page_size=50", token=token)
    n_ah = len((ah or {}).get("items") or (ah or {}).get("tickets") or [])
    _, cp = call("GET", "/api/v1/tickets?status=crm_pending&page=1&page_size=50", token=token)
    items = (cp or {}).get("items") or (cp or {}).get("tickets") or []
    check("filter awaiting_human empty", n_ah == 0, f"count={n_ah}")
    check("filter crm_pending has our ticket",
          any(x.get("id") == tid for x in items), f"count={len(items)}")

    print("── 8. legal transition: crm_pending -> resolved ──")
    s, r = call("PATCH", f"/api/v1/tickets/{tid}/status",
                {"status": "resolved", "reason": "crm_resolved"}, token)
    check("resolved accepted", s == 200 and r.get("new_status") == "resolved",
          f"http={s} {str(r)[:120]}")
    _, cur = call("GET", f"/api/v1/tickets/{tid}", token=token)
    check("status persisted", (cur or {}).get("status") == "resolved",
          f"status={(cur or {}).get('status')}")

    print("── 9. mock CRM pushes ──")
    hits = mock_crm_hits()
    if hits:
        info("mock CRM received", f"{len(hits)} push(es): " + "; ".join(
            f"{h['body'].get('event', '?')}/{h['body'].get('ticket_id', '?')[:8]}"
            for h in hits[:5]))
    else:
        info("mock CRM received nothing", "expected locally — the pipeline "
             "escalation branch needs LLM keys; the status-machine checks "
             "above are the authoritative pass/fail signals")

    print("── summary ──")
    hard = [r for r in results if r[1] is not None]
    failed = [r for r in hard if not r[1]]
    for name, ok, detail in hard:
        print(f"   {'PASS' if ok else 'FAIL'}  {name}")
    print(f"RESULT: {len(hard) - len(failed)}/{len(hard)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
