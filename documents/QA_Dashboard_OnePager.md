# AI QA — The Report Card (one-pager)

**The pitch in one line:** every conversation your AI handles gets graded the
moment it ends — and you open one screen to see the grades.

## What the client sees

A single screen with four numbers at the top:

| Panel | What it says |
|---|---|
| Average quality | Your score out of 100, recomputed after every conversation |
| Conversations graded | 100% coverage — not a 2% sample |
| Flagged for review | The suspicious few, **each with the reason why** |
| Double-checks ran | How many background reviews ran vs. the daily cap |

Below it: the problems caught (click a row, see why), which technique won,
knowledge gaps, quality per language, volume, and an honest "how the grading
runs" strip.

## How it runs (the honest version)

1. **Layer 1 — the checklist ($0).** Every reply passes a pure-code 5-point
   checklist (structure, logic, brand voice, tone, PII). No AI calls. No cost.
   Milliseconds.
2. **Hard evidence ($0).** Facts are recorded: the same question asked twice,
   angry wording, repeat visits. When in doubt, the conversation is flagged —
   never silently passed.
3. **Layer 2 — the officer (capped).** Only flagged conversations (typically
   ~10%) get ONE cheap background review, capped at 500/day. The customer
   never waits; the check happens after the conversation ends. If the officer
   says "fail", a stronger model double-checks it once.

## The rules it lives by

- **Locked drawer:** every grade is stamped with the client's ID. A client
  can never see another client's conversations — enforced at the database
  layer, not by hiding buttons.
- **Fail-open:** QA can never break a conversation. If QA is down, support
  works exactly as before.
- **No overclaims:** we say what the screen shows. No escalation promises,
  no shadow mode, no competitor numbers.

## API (live in the product)

- `GET /api/qa/summary?days=30` — the KPI row
- `GET /api/qa/conversations?flagged=true` — the problems panel
  (both locked to the authenticated caller's company)

## Cost picture

Grading: **$0** (pure code). Officer reviews at 20k tickets/month: about
**$0.5–2/month**, hard-capped. The screen shows exactly how many ran.
