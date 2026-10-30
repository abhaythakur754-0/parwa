# loop.md — PARWA Daily Learning Loop (operating manual)

Owner-readable, AI-executable. Every session on this repo runs by this file.
Read together with CLAUDE.md (how to code) and AGENTS.md (how to be lazy).
STATE.md holds the current state; worklog.md holds the history.

## The idea in one paragraph

We cannot afford GPU training — and we do not need it. The AI (Z.ai) is the
rented brain; this repo is the owned memory. Every day, ONE long session:
read the memory, close gaps, write back what we learned. Every day leaves a
receipt in db/learning.db, so "Parwa improves day by day" is a provable
fact, not a slogan.

## The daily ritual (never skipped)

1. BRIEF — `python3 scripts/learning_loop.py briefing`
   Shows rules, ranked gaps, last receipt. The AI proposes today's plan
   from the top gaps. The OWNER approves or changes it.
2. BUILD — work the approved gaps (graphify first, per CLAUDE.md).
3. WRITE-BACK — record everything learned (commands below). NOTHING
   important stays only in chat: if it matters, it goes in the memory.
4. COMMIT — `log-day` receipt + `git commit` + `git push`.
   The session is NOT finished until the receipt exists.

## Iron rules

- Never skip `log-day`. A day with work but no receipt breaks the proof.
- Nothing important stays in chat. Memory = db/learning.db + STATE.md +
  worklog.md.
- Client needs: config rows first (tenant_policies); new code/tools only
  when config cannot express it.
- The AI proposes; the OWNER decides (gap priority, risky actions, open
  questions such as notifier channel / approval mode — see gap #3).
- One long session daily (owner's rhythm — there is no "small nightly").

## Cold start (brand-new AI session that knows nothing)

Owner triggers the loop by saying: **"go through loop.md"** (or
"continue Parwa", plus repo URL + access token if needed).
The AI then, on its own:
1. Clone/pull the repo. Read CLAUDE.md, AGENTS.md, and this file.
2. Run `python3 scripts/learning_loop.py briefing`.
3. Read STATE.md (current state) and the worklog.md tail (recent history).
4. Propose today's plan from the top gaps. Wait for owner approval.
5. Run the daily ritual above.

NOTE: CLAUDE.md stays purely about coding rules — the loop is invoked
explicitly through this file, never mixed into CLAUDE.md.

## Command cheat sheet (scripts/learning_loop.py)

    briefing          rules + ranked gaps + last receipt (session starts here)
    add-lesson        mistake -> rule (symptom --rule ... [--cat bug|design|process|testing])
    hit-lesson ID     the rule saved us again (bump its count)
    retire-lesson ID  rule got old (leaves the briefing)
    add-gap           missing part / bug / idea (--priority 1|2|3 --source discussion|ticket|ui_test|prod)
    start-gap ID      claim a gap (in_progress)
    done-gap ID       close a gap (done + date)
    drop-gap ID       wontfix
    decide            record a decision (--what --why --rejected)
    log-day           today's receipt (--done --next)  <- NEVER SKIP
    export            dump the whole memory as JSON
    selfcheck         built-in test (17 checks, runs on a temp DB)

## Where everything lives

    db/learning.db             the memory (committed — travels with the repo)
    scripts/learning_loop.py   the tool (stdlib only, selfcheck inside)
    STATE.md                   current state + history sections
    worklog.md                 narrative log, one entry per task

## Data rules

- Dates are IST (Asia/Calcutta).
- Gap priority: 1 = deploy blockers, 2 = medium, 3 = low.
- Lessons are short RULES, not stories; retire old ones in-session.
