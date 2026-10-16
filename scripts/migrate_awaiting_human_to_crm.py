"""
Migrate legacy awaiting_human tickets to crm_pending (HumanReplacement).

Runs against the LIVE backend via the same REST API the dashboard uses.
Prerequisite: the "Remove awaiting_human" commit is deployed to Render
(the new ticket_service allows awaiting_human -> crm_pending).

What it does:
  1. Logs in as the livetest tenant (JWT).
  2. Lists all tickets with status=awaiting_human.
  3. PATCHes each one to status=crm_pending with reason=crm_escalation
     (the state machine's HumanReplacement transition).
  4. Re-lists and prints the final status counts + CRM metadata.

Usage:
    python3 scripts/migrate_awaiting_human_to_crm.py
"""

import json
import sys
import urllib.request

BACKEND = "https://parwa-backend.onrender.com"
EMAIL = "parwa.livetest+1790404319@gmail.com"
PASSWORD = "Livetest#2026x"
ORIGIN = "https://parwa.buzz"


def _req(method: str, path: str, token: str = None, body: dict = None):
    url = f"{BACKEND}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Origin", ORIGIN)
    req.add_header("Referer", f"{ORIGIN}/")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    print("── login ──")
    auth = _req("POST", "/api/auth/login", body={"email": EMAIL, "password": PASSWORD})
    token = auth.get("access_token") or auth.get("token")
    if not token:
        print("LOGIN FAILED:", json.dumps(auth)[:300])
        return 1
    print("   ok")

    print("── find awaiting_human tickets ──")
    listing = _req("GET", "/api/v1/tickets?status=awaiting_human&page=1&page_size=50", token)
    items = listing.get("items") or listing.get("tickets") or []
    ids = [t["id"] for t in items]
    print(f"   found {len(ids)}: {ids}")

    migrated = []
    for tid in ids:
        try:
            res = _req("PATCH", f"/api/v1/tickets/{tid}/status", token,
                       {"status": "crm_pending", "reason": "crm_escalation"})
            migrated.append((tid, res.get("new_status")))
            print(f"   PATCH {tid[:8]} -> {res.get('new_status')}")
        except Exception as exc:  # noqa: BLE001
            print(f"   PATCH {tid[:8]} FAILED: {str(exc)[:200]}")

    print("── verify ──")
    for status in ("awaiting_human", "crm_pending"):
        data = _req("GET", f"/api/v1/tickets?status={status}&page=1&page_size=50", token)
        n = len(data.get("items") or data.get("tickets") or [])
        print(f"   status={status}: {n} tickets")

    print("── done ──")
    return 0 if migrated else (1 if ids else 0)


if __name__ == "__main__":
    sys.exit(main())
