#!/usr/bin/env python3
"""
Create 10 UNIQUE + COMPLICATED + REALISTIC tickets on the LIVE production
backend (parwa-backend.onrender.com) via the REAL ticket API — the exact
same flow the parwa.buzz dashboard uses. NOT direct DB inserts: every
ticket goes through the full AI pipeline (classification, agent routing,
KB retrieval, tool calls, SLA, analytics).

Auth: user's live tenant account (company 2e8c89db-…).
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "https://parwa-backend.onrender.com"
EMAIL = "parwa.livetest+1790404319@gmail.com"
PASS = "Livetest#2026x"
TOKEN = {"v": None}
CREATED = []


def call(method, path, body=None, auth=True, timeout=90):
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
    except Exception as e:
        return 0, {"error": str(e)}


def login():
    s, d = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASS}, auth=False)
    if s != 200:
        print(f"LOGIN FAIL http={s}: {str(d)[:200]}", flush=True)
        sys.exit(1)
    TOKEN["v"] = (d.get("tokens") or {}).get("access_token") or d.get("access_token")
    print(f"login OK (token {len(TOKEN['v'] or '')} chars)", flush=True)


def wake_backend():
    print("waking Render backend (free tier cold start ~60-90s)...", flush=True)
    for i in range(36):
        s, d = call("GET", "/health", auth=False, timeout=30)
        if s == 200:
            print(f"backend awake after {i * 5}s: {str(d)[:100]}", flush=True)
            return True
        time.sleep(5)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 10 UNIQUE, COMPLICATED, REALISTIC TICKETS
# Real customer voice, real specifics (order ids, amounts, dates, txn refs),
# multi-issue overlap, real emotional stakes. No two alike.
# ─────────────────────────────────────────────────────────────────────────────
TICKETS = [
    # 1 — billing: double charge + partial refund + pending bank hold + chargeback ultimatum
    dict(
        subject="Charged twice for order #TW-40812 - refund only covered half and bank shows a THIRD pending hold",
        description=(
            "I placed order #TW-40812 (Aurora Desk Lamp, charcoal) on 2nd September for $148.90. "
            "My bank statement shows the amount captured TWICE on 2nd Sep - txn refs TXN-88213-04 and TXN-88214-11. "
            "I contacted support the same day and was told the duplicate would auto-reverse in 3-5 business days. "
            "It is now 12th September. Only $74.45 came back - exactly HALF, not the full duplicate. "
            "Worse, my banking app now shows a THIRD pending authorization for $148.90 dated 10th Sep which I never triggered. "
            "I have already been out of pocket $222.45 for one lamp. I want: (1) full reversal of the remaining $148.90 today, "
            "(2) written explanation of why the third hold appeared, (3) confirmation in writing that my card token has been purged "
            "from your payment vault. If I do not see the reversal within 48 hours I will initiate a chargeback with my bank "
            "and dispute all three transactions, not just one."
        ),
        customer_name="Ritika Sharma", customer_email="ritika.sharma.saves@gmail.com",
        channel="email", priority="high", category="billing",
        tags=["double-charge", "chargeback-risk", "payment-vault"],
        followups=[
            "Checking back on this. My bank has now CONFIRMED the second hold posted permanently (not pending anymore) - ref TXN-88214-11. "
            "And the third authorization converted to a capture this morning. That is $297.80 taken for one $148.90 lamp. "
            "This is day 3 of my 48-hour deadline. I need the reversal confirmation number today, please.",
        ],
    ),
    # 2 — shipping: 19 days in transit + mid-shipment address reroute + carrier runaround
    dict(
        subject="Order #TW-40712 shows 'label created' for 19 days AND I moved apartments - reroute request refused",
        description=(
            "Order #TW-40712 (2x Nimbus Standing Fan, white) was placed on 24th August and paid in full, $329.00. "
            "Tracking has said 'Shipping label created' since 25th August - nineteen days with zero movement. "
            "I contacted the courier (BlueDart) and they told me the parcel was never actually handed to them, "
            "and that only the merchant can open a trace. Your support chat keeps telling me 'in transit, please wait'. "
            "Separately - and this is urgent - I moved apartments on 1st September. My old address is 14B Lakeview Residency, "
            "and the new one is 902 Orchid Towers. I asked for a reroute on 2nd September and was told it's not possible "
            "once shipped, but the parcel has NOT shipped according to the courier themselves. "
            "I need you to either (a) ship to the new address with the trace reopened, or (b) cancel and refund in full today. "
            "I've already waited three weeks. Please stop sending template replies and give me a real answer."
        ),
        customer_name="Daniel Osei", customer_email="d.osei.outbox@proton.me",
        channel="chat", priority="high", category="shipping",
        tags=["lost-in-transit", "address-change", "carrier-trace"],
        followups=[
            "Update - I called BlueDart again an hour ago. They now say the parcel is being 'returned to sender' WITHOUT ever "
            "attempting delivery, and that you (the merchant) requested the return on 8th September. Nobody informed me. "
            "So where is my refund for the return leg? Please confirm in writing that once it lands at your warehouse I get "
            "a full refund within 48h, or just reship to Orchid Towers. I am losing patience.",
        ],
    ),
    # 3 — refund: damaged item + expired return window + broken prior promise + missing loyalty points (4 issues in one)
    dict(
        subject="Aurora lamp arrived SHATTERED, return window 'expired' 2 days ago, promised extension ignored, and 1,200 loyalty points never credited",
        description=(
            "Three problems, one order (#TW-40589, 21st August, $186.40):\n\n"
            "1) The Aurora Table Lamp arrived shattered - both glass panels broken. I photographed everything including the box "
            "with the 'FRAGILE' sticker barely attached. Photos available on request.\n\n"
            "2) I opened a return request on 8th September and your system rejected it saying the 14-day window closed on 4th September. "
            "BUT on 29th August your agent (chat transcript ref CH-99821) explicitly told me: 'no problem, we have extended your "
            "return window to 15th September because of the shipping delay'. That promise is in your own transcript. Honoring it "
            "should not be negotiable.\n\n"
            "3) My order was eligible for 1,200 loyalty points (Gold tier, 2x multiplier). My points balance shows zero credited "
            "from this order. My friend who ordered the same day got hers.\n\n"
            "I want: the return approved under the promised extension with a prepaid label (I should NOT pay shipping for a "
            "item that arrived broken), full refund or replacement - my choice per your own policy, and the 1,200 points credited. "
            "If the transcript ref helps: account email is this one, order 21 Aug."
        ),
        customer_name="Priya Venkatesh", customer_email="priya.venkatesh.mail@gmail.com",
        channel="email", priority="high", category="refund",
        tags=["damaged-item", "return-window", "agent-promise", "loyalty-points"],
        followups=[
            "Adding to this: I found the exact chat transcript reference - it is CH-99821, 29th August, 4:47 PM. The agent's name "
            "shown was 'Meera'. Please pull the transcript instead of asking me to repeat everything a third time. "
            "Also flagging: if the replacement ships, it must go to my office address (I put this in the original return request) "
            "because nobody signs for parcels at my flat during the day.",
        ],
    ),
    # 4 — technical: webhook integration broken after plan upgrade, 502 + signature mismatch, SLA credit demand
    dict(
        subject="After upgrading to Growth plan our webhook endpoint gets 502 + intermittent signature verification failure - production checkout down 40+ min",
        description=(
            "We upgraded from Starter to Growth on 9th September (invoice INV-2026-0912). Since then our order.created webhook "
            "integration is broken:\n\n"
            "- POSTs to our endpoint https://api.brightlane.io/hooks/parwa return 502 roughly 60% of the time (Cloudflare logs "
            "show origin timeout, not our app - your side never completes the TLS handshake in those cases)\n"
            "- When a request DOES arrive, X-Parwa-Signature verification fails intermittently (same secret, same code path - "
            "works, then fails, then works). We suspect key rotation mid-flight or a second signing instance.\n"
            "- Retry behavior looks wrong: we got the SAME event ID (evt_778102) delivered 11 times in 4 minutes, which our "
            "idempotency layer catches but which blew through our WAF rate limit.\n\n"
            "Impact: our production checkout has been degraded for 40+ minutes twice this week. We are on the Growth plan "
            "specifically for the 99.9% webhook SLA. We need: (1) root cause, (2) confirmation whether signing keys were rotated "
            "on 9th-10th Sep, (3) the incident report, and (4) SLA credit per your uptime policy. Our eng lead is "
            "eng@brightlane.io - happy to share request IDs and HMAC samples privately."
        ),
        customer_name="Marcus Chen", customer_email="marcus.chen@brightlane.io",
        channel="chat", priority="critical", category="technical",
        tags=["webhooks", "integration-broken", "sla-credit", "production-down"],
        followups=[
            "Escalating: since 14:32 UTC signature verification is now failing on 100% of deliveries, not intermittent. "
            "Request IDs from our logs: req_55120, req_55121, req_55124 (all evt_778190, all sig-reject). "
            "If keys were rotated, we were never notified - that alone breaks your own docs section 4.2 which promises "
            "14-day advance notice. Please treat this as a P1 - our checkout is fully down now, not degraded.",
        ],
    ),
    # 5 — billing/cancellation: billed after cancellation + duplicate accounts split history
    dict(
        subject="Cancelled in March but billed April AND May, plus I have two accounts and my order history is split between them",
        description=(
            "I cancelled my Plus subscription on 28th March (confirmation email attached, ref CAN-3391). "
            "I was still billed $19.00 on 15th April and $19.00 on 15th May - invoices INV-2026-0445 and INV-2026-0502. "
            "That is $38.00 taken after cancellation. I want both refunded.\n\n"
            "Second problem, possibly related: somewhere along the way I ended up with TWO accounts. My original was "
            "signup with Google (this email). At some point a password-based duplicate was created with the SAME email. "
            "My March order (#TW-39120) sits in one account and my June order (#TW-41902) sits in the other. "
            "Support last month told me accounts 'cannot be merged' which contradicts your help center article HC-114 that "
            "explicitly describes a merge flow.\n\n"
            "What I need: (1) refund of the two post-cancellation invoices, (2) the two accounts merged into one with full "
            "order history, (3) written confirmation that the subscription is fully cancelled with no auto-renew, and "
            "(4) please fix whatever billing logic charged me after a confirmed cancellation - this looks like a bug, "
            "not a one-off."
        ),
        customer_name="Aarav Mehta", customer_email="aarav.mehta.work@outlook.com",
        channel="email", priority="high", category="billing",
        tags=["billed-after-cancel", "duplicate-accounts", "refund-due", "possible-bug"],
    ),
    # 6 — shipping: wrong variant + exchange OOS + wedding deadline (SMS, terse real voice)
    dict(
        subject="WRONG item sent - navy 42 ordered, brown 40 received. Exchange out of stock. Wedding on 28th.",
        description=(
            "Ordered: Lumina Oxford Shirt, NAVY, size 42. Received: BROWN, size 40. Order #TW-40923, delivered 11th Sep. "
            "It is a wedding outfit - the wedding is on 28th September. I tried exchange: system says out of stock until "
            "'next restock' with no date. I do not want a store credit, I want either the right shirt in time or my money "
            "back to buy elsewhere. Please confirm same-day if refund is possible. This is the second wrong item this year "
            "(last time was June, order #TW-37701)."
        ),
        customer_name="Karan Malhotra", customer_email="karan.m.hrs@gmail.com",
        channel="sms", priority="high", category="shipping",
        tags=["wrong-item", "exchange-oos", "deadline-critical"],
        followups=[
            "Also - if you CAN ship navy 42 from any warehouse, I will pay express. Just tell me today if any warehouse has it. "
            "Checking every few hours, please don't make me call.",
        ],
    ),
    # 7 — complaint/social: courier false delivered + double-rejected dispute + public post + chargeback
    dict(
        subject="Courier marked order #TW-40201 'DELIVERED' with photo at WRONG doorstep - dispute rejected twice. Posted publicly.",
        description=(
            "Order #TW-40201 ($212.75, SoundCore Buds Pro + case) marked delivered 5th September, 2:14 PM per tracking. "
            "The courier's own POD photo shows someone else's doorstep - different building entirely, different door, "
            "different doormat. My building has CCTV; no delivery was attempted that day.\n\n"
            "I filed a dispute on 6th September: REJECTED with 'courier confirms delivery'. I appealed 9th September with "
            "the POD photo annotated showing the wrong building: REJECTED again, same template reply.\n\n"
            "What I am demanding, and it is all documented in your own system: (1) the FULL-resolution POD photo and the "
            "courier's GPS coordinates for the delivery scan - under consumer protection rules you are the merchant of record, "
            "the courier's answer is YOUR problem, not mine; (2) a refund of $212.75; (3) an explanation of how a dispute "
            "gets 'rejected' without anyone comparing the POD photo to my address on file.\n\n"
            "I have posted the POD photo on X/Twitter tagging your handle. It is getting traction. I will file a chargeback "
            "and a consumer forum complaint either way - the difference is whether you resolve this like a company that "
            "cares or get the same outcome with the reputation damage."
        ),
        customer_name="Fatima Noor", customer_email="fatima.noor.99@gmail.com",
        channel="social", priority="critical", category="complaint",
        tags=["false-delivery", "dispute-rejected", "public-complaint", "chargeback-risk"],
        followups=[
            "Second post is up - tagging your support handle this time, and it has 40+ reposts in an hour. Meanwhile your "
            "dispute form rejected my appeal a SECOND time with the same template. I am giving you until Friday. "
            "After that: chargeback + consumer forum + I send the full timeline (with your rejection emails) to the "
            "consumer rights newsletter that just DM'd me. All of this is avoidable. Just refund it.",
        ],
    ),
    # 8 — billing/enterprise: invoice compliance (wrong GSTIN, no PO number, wrong entity) — formal AP tone
    dict(
        subject="Invoice INV-2026-0908 rejected by our AP system - wrong GSTIN, missing PO number, incorrect billing entity name",
        description=(
            "Our accounts payable system has rejected invoice INV-2026-0908 (Growth plan annual, $2,388.00 + GST) for three "
            "compliance reasons:\n\n"
            "1. GSTIN on the invoice reads 27AABCT1234R1Z5 - that is our OLD registration, cancelled in January 2026. "
            "The correct GSTIN is 27AAECV9988M1Z9.\n"
            "2. The invoice carries no PO number. Our PO is PO-2026-07741 and it must appear in the invoice header for "
            "matching. Net-30 payment runs only after a clean 3-way match.\n"
            "3. Billing entity name reads 'TechVision Solutions Pvt Ltd' - the contracted entity is 'TechVision Solutions "
            "LIMITED' (note: Limited, not Pvt Ltd - these are different legal entities and our finance controller will "
            "not process a mismatch).\n\n"
            "Please reissue a corrected invoice (credit note + reissue is fine per your billing FAQ). Until then the "
            "payment is blocked on our side - we would rather fix this now than accrue late-payment friction. "
            "Our finance controller (cc'd conceptually: accounts@techvision.example) needs the corrected document "
            "before 30th September to make this month's payment run."
        ),
        customer_name="Nandini Iyer (Finance)", customer_email="accounts@techvision-solutions.example",
        channel="email", priority="medium", category="billing",
        tags=["invoice-compliance", "gst", "po-number", "enterprise"],
    ),
    # 9 — privacy/GDPR: export + deletion request with open refund conflict (formal legal tone)
    dict(
        subject="GDPR Article 15 & 17 request: full data export + account deletion - and how does deletion interact with my OPEN refund?",
        description=(
            "This is a formal request under GDPR Articles 15 (access) and 17 (erasure) for all personal data you hold "
            "about me, associated with this email address.\n\n"
            "Scope I expect: profile data, both saved addresses, full order history (#TW-38110, #TW-39554, #TW-41230), "
            "all support conversations across email and chat (including internal notes about me, if any - Article 15 "
            "covers those), marketing consent records, and any data shared with processors (your courier and payment "
            "providers).\n\n"
            "Complication I want addressed BEFORE you action anything: I have an OPEN refund request on #TW-41230 "
            "($89.90, returned 8th September, refund not yet received). Clearly I cannot have my account erased while "
            "money is owed to me. So: (a) confirm whether you will complete the refund first and then erase, (b) what "
            "happens to the refund if the account is erased mid-process, and (c) confirm the statutory one-month clock. "
            "My request date is today - I expect substantive response within 30 days per Article 12(3), and I am aware "
            "extension requires justification. Please confirm receipt with a ticket reference."
        ),
        customer_name="Elif Kaya", customer_email="elif.kaya.privacy@proton.me",
        channel="email", priority="medium", category="account",
        tags=["gdpr", "data-export", "erasure", "open-refund-conflict"],
    ),
    # 10 — quality/refund negotiation: batch defect 3/6 units + coupon-vs-refund negotiation + batch investigation
    dict(
        subject="3 of 6 Halo bulbs from SAME batch died within a week - offered 20% coupon, want proportional refund + batch investigation",
        description=(
            "I bought the 6-pack of Halo Smart Bulbs (order #TW-40444, $279.00, delivered 30th August). Three units - "
            "all with batch code QA-2026-0918-B printed on the base - died within 8 days: two won't power on at all, "
            "one connects then drops off the network every few minutes and now won't reset.\n\n"
            "Support offered me a 20% discount coupon on my next purchase. That is not an acceptable remedy for "
            " defective goods - I am out $139.50 of working product either way. Under the Sale of Goods Act "
            "equivalents here, faulty goods within 30 days entitle me to a full remedy of my choosing, not a "
            "discount on future purchases of the very product line that failed.\n\n"
            "What I want: (1) refund of 50% of the order ($139.50) matching the failed units - or full replacement "
            "6-pack from a DIFFERENT batch, my choice; (2) keep the 3 working units as partial use; (3) someone to "
            "actually investigate batch QA-2026-0918-B - three simultaneous failures from one batch is not bad luck, "
            "and if you keep shipping that batch this will be your return-rate problem, not just mine; (4) confirm "
            "the other 3 units' batch codes get registered against my order in case they fail too."
        ),
        customer_name="Jonas Weber", customer_email="j.weber.hamburg@gmail.com",
        channel="chat", priority="high", category="refund",
        tags=["batch-defect", "refund-negotiation", "quality-investigation"],
        followups=[
            "Bad news - a FOURTH unit (batch QA-2026-0918-B as well, ref code on base confirmed) failed this evening, "
            "same no-power symptom. That is 4 of 6 from one batch. And two more units are the SAME batch and just "
            "waiting to die. Please escalate the batch investigation and update my case to full refund of all 6 units. "
            "I am done replacing units one by one.",
        ],
    ),
]


def create_ticket(t):
    body = {
        "subject": t["subject"],
        "description": t["description"],
        "customer_name": t["customer_name"],
        "customer_email": t["customer_email"],
        "channel": t["channel"],
        "priority": t["priority"],
        "category": t["category"],
        "tags": t.get("tags", []),
    }
    for attempt in range(3):
        s, d = call("POST", "/api/v1/tickets", body)
        if s == 201:
            tid = d.get("id") or d.get("data", {}).get("id") or d.get("ticket", {}).get("id")
            return s, tid, d
        if s == 401:
            login(); continue
        if s == 429:
            wait = 35
            print(f"    429 burst protection - waiting {wait}s...", flush=True)
            time.sleep(wait); continue
        if s in (502, 503, 0):
            time.sleep(10); continue
        break
    return s, None, d


def add_followup(tid, text, channel):
    body = {"role": "customer", "content": text, "channel": channel, "is_internal": False}
    for attempt in range(3):
        s, d = call("POST", f"/api/v1/tickets/{tid}/messages", body)
        if s in (200, 201):
            return True
        if s == 401:
            login(); continue
        time.sleep(5)
    return False


def main():
    print("=" * 78)
    print("CREATING 10 UNIQUE + COMPLICATED REAL TICKETS VIA LIVE PRODUCTION API")
    print("=" * 78, flush=True)

    if not wake_backend():
        print("backend did not wake in 3 min - aborting", flush=True)
        return 1
    login()

    print(f"\n{'#':>2} {'status':>4} {'ticket id':<38} {'channel':<7} subject", flush=True)
    print("-" * 110)
    for i, t in enumerate(TICKETS, 1):
        s, tid, d = create_ticket(t)
        marker = "OK " if s == 201 else "!! "
        print(f"{i:>2} {marker} {str(tid)[:36]:<38} {t['channel']:<7} {t['subject'][:58]} [http {s}]", flush=True)
        if tid:
            CREATED.append({"idx": i, "id": tid, "subject": t["subject"],
                            "channel": t["channel"], "priority": t["priority"],
                            "customer": t["customer_name"], "email": t["customer_email"]})
        else:
            print(f"    body: {str(d)[:220]}", flush=True)
        time.sleep(9)  # spacing: avoid burst protection + let pipeline breathe

    # follow-up messages (real multi-turn conversations)
    print("\nAdding realistic follow-up customer messages...", flush=True)
    for entry in CREATED:
        t = TICKETS[entry["idx"] - 1]
        for fu in t.get("followups", []):
            ok = add_followup(entry["id"], fu, t["channel"])
            print(f"  followup -> {entry['id'][:12]}… {'OK' if ok else 'FAILED'}", flush=True)
            time.sleep(6)

    # verify each ticket exists + capture pipeline status
    print("\nVerifying tickets (pipeline state)...", flush=True)
    for entry in CREATED:
        s, d = call("GET", f"/api/v1/tickets/{entry['id']}")
        if s == 200:
            tk = d if isinstance(d, dict) else {}
            st = tk.get("status") or tk.get("data", {}).get("status") or "?"
            pr = tk.get("priority") or tk.get("data", {}).get("priority") or "?"
            intent = tk.get("classification_intent") or tk.get("data", {}).get("classification_intent") or "-"
            entry["verify"] = {"http": s, "status": st, "priority": pr, "intent": intent}
            print(f"  {entry['id'][:12]}… status={st:<16} priority={pr:<9} intent={intent}", flush=True)
        else:
            entry["verify"] = {"http": s}
            print(f"  {entry['id'][:12]}… verify http={s}", flush=True)
        time.sleep(2)

    with open("/home/z/my-project/tickets-created.json", "w") as f:
        json.dump({"created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                   "count": len(CREATED), "tickets": CREATED}, f, indent=2)

    print("\n" + "=" * 78)
    print(f"DONE: {len(CREATED)}/10 tickets created via REAL API (full AI pipeline)")
    print("Saved manifest -> /home/z/my-project/tickets-created.json")
    print("=" * 78, flush=True)
    return 0 if len(CREATED) == 10 else 1


if __name__ == "__main__":
    sys.exit(main())
