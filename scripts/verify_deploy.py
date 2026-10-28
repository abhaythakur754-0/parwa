#!/usr/bin/env python3
"""Deploy verification on NEW production code (post 083cf6d+312cf7d).
Tests: (A) duplicate ticket -> 409 not 500  (B) shipping KB question -> RESOLVED."""
import json, sys, time
import urllib.request, urllib.error

BASE = "https://parwa-backend.onrender.com"
EMAIL = "parwa.livetest+1790404319@gmail.com"
PASS = "Livetest#2026x"
TOKEN = {"v": None}


def call(method, path, body=None, auth=True, timeout=120):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Origin", "https://parwa.buzz")
    req.add_header("Referer", "https://parwa.buzz/")
    if auth and TOKEN["v"]:
        req.add_header("Authorization", "Bearer " + TOKEN["v"])
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}


def login():
    s, d = call("POST", "/api/auth/login",
                {"email": EMAIL, "password": PASS}, auth=False)
    if s != 200:
        print("LOGIN FAIL", s, str(d)[:200]); sys.exit(1)
    TOKEN["v"] = (d.get("tokens") or {}).get("access_token") or d.get("access_token")
    print("login OK, token len", len(TOKEN["v"] or ""))


def create(subject, desc, email):
    return call("POST", "/api/v1/tickets", {
        "subject": subject, "description": desc,
        "customer_name": "Deploy Verify", "customer_email": email,
        "channel": "email", "priority": "medium",
    })


def get_ticket(tid):
    return call("GET", f"/api/v1/tickets/{tid}")


def main():
    results = []

    # ---- TEST A: duplicate submission -> expect 409 DUPLICATE_TICKET ----
    subj = "deploy verify duplicate probe " + str(int(time.time()))
    desc = "Body for duplicate probe. Order not arrived, please check status."
    email = "deployverify.dup+" + str(int(time.time())) + "@example.com"
    s1, d1 = create(subj, desc, email)
    tid1 = (d1.get("id") or d1.get("data", {}).get("id")
            or d1.get("ticket", {}).get("id")) if isinstance(d1, dict) else None
    print(f"A1 create: http={s1} id={tid1}")
    s2, d2 = create(subj, desc, email)
    code = (d2.get("code") or d2.get("detail", {}).get("code")
            if isinstance(d2, dict) else None)
    print(f"A2 duplicate: http={s2} code={code} body={str(d2)[:200]}")
    ok = (s2 == 409 and code == "DUPLICATE_TICKET")
    results.append(("A: dup -> 409 DUPLICATE_TICKET (was 500)", ok,
                    f"first={s1}, second={s2}/{code}"))

    # ---- TEST B: shipping KB question -> expect RESOLVED with KB answer ----
    subj2 = "Where is my order 7788 shipping status"
    desc2 = ("Hi, I ordered order 7788 last week and it still shows unshipped. "
             "When will it arrive? I need it for a gift.")
    email2 = "deployverify.kb+" + str(int(time.time())) + "@example.com"
    s3, d3 = create(subj2, desc2, email2)
    tid2 = (d3.get("id") or d3.get("data", {}).get("id")
            or d3.get("ticket", {}).get("id")) if isinstance(d3, dict) else None
    print(f"B1 create: http={s3} id={tid2}")

    final = None
    if tid2:
        for i in range(36):  # up to ~6 min
            time.sleep(10)
            try:
                TOKEN["v"] = TOKEN["v"]  # token fresh enough
                s4, d4 = get_ticket(tid2)
                if s4 == 403:
                    login()
                    s4, d4 = get_ticket(tid2)
                if s4 != 200:
                    continue
                st = (d4.get("status") or d4.get("data", {}).get("status")
                      or d4.get("ticket", {}).get("status"))
                print(f"  poll{i}: status={st}")
                if st and st.lower() not in ("processing", "in_progress", "open", "pending"):
                    final = d4
                    break
            except Exception as e:
                print("  poll err", e)

    kb_ok = False
    detail = ""
    if final:
        st = final.get("status") or final.get("data", {}).get("status")
        msgs = (final.get("messages") or final.get("data", {}).get("messages")
                or final.get("ticket", {}).get("messages") or [])
        ai = ""
        for m in msgs:
            if (m.get("sender") or m.get("author") or "") in ("ai", "assistant", "system"):
                ai = m.get("body") or m.get("content") or m.get("text") or ""
                if ai:
                    break
        detail = f"status={st} ai_reply={ai[:180]!r}"
        low = ai.lower()
        kb_ok = (str(st).lower() == "resolved") and (
            "5-7" in low or "5 to 7" in low or "2 days" in low
            or "ship" in low)
    results.append(("B: shipping KB question -> RESOLVED w/ KB answer", kb_ok, detail))

    print("\n===== VERDICT =====")
    for name, ok, det in results:
        print(("PASS " if ok else "FAIL "), name, "|", det)
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    login()
    sys.exit(main())
