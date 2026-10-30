# Ghostwriter — fills the gaps your QA finds (one-pager)

**The pitch in one line:** the AI tells you what it doesn't know, then drafts
the missing help article for your approval.

## The problem it solves

The Report Card's "Knowledge gaps found" panel lists every topic where the
agent kept failing — e.g. *"EU warranty claims — failed 31× — no help article
exists."* Today that list is a to-do nobody does. The gap stays for months.

## How it works

1. You click **"Draft this gap"** on a gap.
2. The system gathers **only your own material**: your recent flagged
   conversations on that topic + the documents you uploaded.
3. ONE cheap AI call writes the draft article. On-demand only — no background
   burn, a few cents per draft, hard daily cap (50/day).
4. The draft lands as **"Draft — waiting for your approval"**, with the
   sources it used listed.
5. You read it. **Approve** or **Needs work**. That is the whole feature.

## The rules it lives by

- **Human approval only.** Nothing auto-publishes — ever. We say "drafts for
  your approval", never "writes articles by itself".
- **Locked drawer:** drafts are written from YOUR conversations and YOUR
  documents only, stamped with your company ID. Approved/rejected via
  endpoints that physically cannot touch another client's drafts.
- **It never invents policy.** If your documents don't cover something, the
  draft says what is unknown instead of guessing.
- **Customers never see it.** It is a back-office tool.
- **Cost is capped and visible.** One LLM call per draft, daily cap,
  drafts counted in the drafts table itself — zero new infrastructure.

## API (live in the product)

- `POST /api/ghostwriter/drafts` — draft an article for a topic
- `GET /api/ghostwriter/drafts` — your drafts, newest first
- `POST /api/ghostwriter/drafts/{id}/approve` — record your approval
- `POST /api/ghostwriter/drafts/{id}/reject` — record your rejection
  (all locked to the authenticated caller's company)

## Where this goes next (roadmap, not promises)

Approved drafts feeding the live knowledge base automatically, A/B testing
draft vs. old article by real QA scores — each step ships only after you
approve it.
