#!/usr/bin/env python3
"""PARWA Learning Loop — the daily-improvement engine (no GPU, no magic).

The loop: ONE session per day, every day.

  1. BRIEF       python3 scripts/learning_loop.py briefing
  2. BUILD       close gaps with the AI assistant (long session, owner's call)
  3. WRITE-BACK  add-lesson / add-gap / decide / log-day   (never skip!)
  4. COMMIT      git commit + push  ->  memory travels with the repo

Storage: db/learning.db — plain stdlib sqlite3, committed to git so every
session/machine reads the same truth and the "we improve day by day" claim
has receipts.

Ponytail notes: stdlib only (rung 3), single file, parameterized SQL.
Learned rule applied: we never build sqlite URL strings — connect() takes a
filesystem path directly, so the 3-slash/4-slash URL bug class cannot exist.
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Calcutta")
except Exception:  # pragma: no cover - old pythons without zoneinfo
    IST = timezone(timedelta(hours=5, minutes=30))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def db_path() -> str:
    return (os.environ.get("PARWA_LEARNING_DB")
            or os.path.join(REPO_ROOT, "db", "learning.db"))


def today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  category TEXT NOT NULL,            -- bug | design | process | testing
  symptom TEXT NOT NULL,
  root_cause TEXT NOT NULL DEFAULT '',
  rule TEXT NOT NULL,
  times_hit INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS gaps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'discussion',
  priority INTEGER NOT NULL DEFAULT 2,   -- 1 high, 2 medium, 3 low
  status TEXT NOT NULL DEFAULT 'open',   -- open | in_progress | done | wontfix
  closed_date TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  what TEXT NOT NULL,
  why TEXT NOT NULL DEFAULT '',
  rejected TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS daily_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  done TEXT NOT NULL,
  next TEXT NOT NULL DEFAULT ''
);
"""


def connect() -> sqlite3.Connection:
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)  # idempotent: fresh clone just works
    return con


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def one(con: sqlite3.Connection, sql: str, args: tuple = ()) -> sqlite3.Row:
    row = con.execute(sql, args).fetchone()
    if row is None:
        die(f"not found: {sql} {args}")
    return row


# ---------------------------------------------------------------- seed data
# Real history: tasks 36/40/41/42/43/44 + owner discussions (2026-10-30).
SEED_LESSONS = [
    ("2026-07-25", "bug",
     "Demo registered tools but the DB had 0 rows",
     "sqlite URL with 3 slashes is a RELATIVE path — writes went to a throwaway file, silently",
     "Absolute sqlite URLs need 4 slashes (sqlite:////abs/path). After any DB write, run a SELECT COUNT to verify before declaring success.",
     2),
    ("2026-07-25", "bug",
     "Crash: NoneType not subscriptable on journal['ticket']['id']",
     "Pipeline steps can be skipped, so journal or ticket can be None",
     "Guard every optional pipeline result: (journal or {}).get(...). Never trust that a step ran.",
     1),
    ("2026-07-26", "design",
     "Novel write-capability ticket died at test stage with no recovery path",
     "No fallback existed for never-seen capabilities; repair fixes shape, not absence",
     "Every novel capability gets the universal fallback template (echo-backed recorder). Write-risk actions always pass the approval gate.",
     1),
    ("2026-07-26", "bug",
     "LLM repair output was pasted without checking its shape",
     "LLM can return prose or a wrong function signature",
     "Shape-guard all LLM output before use: repair transform must match r'^\\s*\\(\\s*sourceData\\s*\\)\\s*=>\\s*\\{'.",
     1),
    ("2026-07-26", "process",
     "Long background test runs died silently",
     "Sandbox reaps nohup/background processes",
     "Run long tests in the foreground under `timeout N python3 -u`; log to console, not only to files.",
     1),
    ("2026-07-26", "bug",
     "Tool-reuse path crashed on an empty result",
     "str(reuse_res or {}).get('tool_id') — str() of a dict then .get is always wrong",
     "Never str() a dict to read fields. Use res.get('tool_id', '') with explicit defaults.",
     1),
    ("2026-10-29", "process",
     "The chat gateway ate literal '[m' sequences — looked like 'const essages' corruption in 5 files",
     "ANSI-strip artifact in displayed/typed text created the illusion of broken code",
     "Never trust displayed '[messages' vs 'essages' — verify file contents with od -c before 'fixing' anything.",
     1),
]

SEED_GAPS = [
    ("Rotate expired Supabase credentials + set DATABASE_URL on the hosting platform",
     "STATE.md BLOCKER: backend cannot boot / self-heal without it. Owner action on Render/Vercel + Supabase.",
     "prod", 1),
    ("Build tenant_policies table: per-client ticket reactions",
     "Same ticket type, different reaction per client. Machinery shared, reactions are data rows. Config first, code only when config cannot express it.",
     "discussion", 2),
    ("Ticket notifier: message the client on every ticket state change",
     "ticket_messages table + formatter; includes the 'not sure' honesty message. BLOCKED on owner answers: channel (in-app/email/WhatsApp) and approval-required-or-inform-only.",
     "discussion", 2),
    ("Deployment/update routine: backup DB before schema changes, quiet-hours restarts, test before deploy",
     "SQLite locks on write — schema migrations are the dangerous step. Owner still to decide: VPS 24/7 vs current hosting.",
     "discussion", 2),
    ("Audit ~51 task decorators declaring queue='default'/'billing' not in QUEUE_NAMES",
     "Residual risk from STATE.md: silent queue starvation class of bugs.",
     "prod", 3),
    ("Wire top-level tests/ suites into CI",
     "192 unit + 12 integration suites exist but .github/workflows/ci.yml runs only backend tests.",
     "prod", 3),
    ("Real Razorpay keys for the payments preset",
     "Creds are tool INPUTS — no redeploy needed. Only remaining gap from the tool-factory task 36.",
     "prod", 3),
    ("Compile Rust parwa_core before performance-sensitive deploy",
     "Source exists but NOT compiled; pure-Python fallbacks active. Run `maturin develop --release`.",
     "prod", 3),
]

SEED_DECISIONS = [
    ("2026-10-30",
     "Learning loop = ONE long session daily; memory lives in the repo (db/learning.db, committed)",
     "Recording while fresh prevents repeated mistakes; committed DB = every session reads the same truth and 'improve day by day' has receipts",
     "GPU fine-tuning (costly, bad for facts); backend ai_wiki_entries (product feature on expired Supabase creds — wrong rung)"),
    ("2026-10-30",
     "Per-client behavior: config rows first, new code/tools only when config cannot express it",
     "A policy row is instant; per-client code multiplies maintenance forever",
     "Hardcoded per-client if-branches in the pipeline"),
    ("2026-10-30",
     "Only one AI client (Z.ai) works on Parwa",
     "Owner decision — single source of truth, no view drift",
     ""),
]

SEED_DAY = ("Built the learning loop itself: db/learning.db + scripts/learning_loop.py "
            "(stdlib sqlite, selfcheck). Seeded 7 rules / 8 gaps / 3 decisions from "
            "tasks 36-44 + owner discussions.",
            "Owner says 'continue Parwa' -> briefing -> pick top gap.")


# ----------------------------------------------------------------- commands
def cmd_init(_args) -> None:
    con = connect()
    counts = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("lessons", "gaps", "decisions", "daily_log")]
    print(f"OK init {db_path()} | lessons={counts[0]} gaps={counts[1]} "
          f"decisions={counts[2]} daily_log={counts[3]}")


def cmd_seed(_args) -> None:
    con = connect()
    if con.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] \
            or con.execute("SELECT COUNT(*) FROM gaps").fetchone()[0] \
            or con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]:
        print("already seeded - skip (seed is one-time)")
        return
    con.executemany(
        "INSERT INTO lessons(date,category,symptom,root_cause,rule,times_hit) "
        "VALUES (?,?,?,?,?,?)", SEED_LESSONS)
    con.executemany(
        "INSERT INTO gaps(date,title,detail,source,priority) VALUES (?,?,?,?,?)",
        [(today(), g[0], g[1], g[2], g[3]) for g in SEED_GAPS])
    con.executemany(
        "INSERT INTO decisions(date,what,why,rejected) VALUES (?,?,?,?)",
        SEED_DECISIONS)
    con.execute("INSERT INTO daily_log(date,done,next) VALUES (?,?,?)",
                (today(), *SEED_DAY))
    con.commit()
    # Learned rule #1: verify writes with a COUNT before declaring success.
    counts = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("lessons", "gaps", "decisions", "daily_log")]
    print(f"seeded + verified: lessons={counts[0]} gaps={counts[1]} "
          f"decisions={counts[2]} daily_log={counts[3]}")


def cmd_briefing(args) -> None:
    con = connect()
    print(f"=== PARWA DAILY BRIEFING — {today()} ({now_ist()}) ===")
    print(f"db: {db_path()}\n")

    rules = con.execute(
        "SELECT * FROM lessons WHERE status='active' "
        "ORDER BY times_hit DESC, date DESC, id DESC LIMIT ?",
        (args.rules_limit,)).fetchall()
    print(f"RULES THAT KEEP US SAFE (top {len(rules)} by hits):")
    for r in rules:
        print(f"  #{r['id']} [{r['category']}] {r['rule']} "
              f"(saved us x{r['times_hit']}, {r['date']})")
    if not rules:
        print("  (none yet)")

    gaps = con.execute(
        "SELECT * FROM gaps WHERE status IN ('open','in_progress') "
        "ORDER BY priority ASC, date ASC, id ASC").fetchall()
    p1 = sum(1 for g in gaps if g["priority"] == 1)
    print(f"\nOPEN GAPS ({len(gaps)} open, {p1} high):")
    for g in gaps:
        mark = "[~]" if g["status"] == "in_progress" else "[ ]"
        print(f"  {mark} #{g['id']} P{g['priority']} ({g['source']}, "
              f"{g['date']}) {g['title']}")
    if not gaps:
        print("  (none — add some with add-gap)")

    last = con.execute(
        "SELECT * FROM daily_log ORDER BY id DESC LIMIT 1").fetchone()
    print("\nLAST SESSION:")
    if last:
        print(f"  {last['date']} done: {last['done']}")
        print(f"  next: {last['next']}")
    else:
        print("  (no sessions logged yet)")

    decs = con.execute(
        "SELECT * FROM decisions ORDER BY id DESC LIMIT 3").fetchall()
    print("\nRECENT DECISIONS:")
    for d in decs:
        line = f"  {d['date']} — {d['what']}"
        if d["why"]:
            line += f" | why: {d['why']}"
        print(line)

    done = con.execute(
        "SELECT COUNT(*) FROM gaps WHERE status='done'").fetchone()[0]
    n_rules = con.execute(
        "SELECT COUNT(*) FROM lessons WHERE status='active'").fetchone()[0]
    print(f"\nTotals: {n_rules} active rules | {len(gaps)} open gaps "
          f"| {done} closed")


def cmd_add_lesson(a) -> None:
    con = connect()
    cur = con.execute(
        "INSERT INTO lessons(date,category,symptom,root_cause,rule,times_hit) "
        "VALUES (?,?,?,?,?,?)",
        (today(), a.cat, a.symptom, a.root, a.rule, a.hits))
    con.commit()
    print(f"lesson #{cur.lastrowid} added ({a.cat})")


def cmd_hit_lesson(a) -> None:
    con = connect()
    les = one(con, "SELECT id, times_hit FROM lessons WHERE id=?", (a.id,))
    con.execute("UPDATE lessons SET times_hit=times_hit+1 WHERE id=?",
                (a.id,))
    con.commit()
    print(f"lesson #{a.id} -> saved us x{les['times_hit'] + 1}")


def cmd_retire_lesson(a) -> None:
    con = connect()
    one(con, "SELECT id FROM lessons WHERE id=?", (a.id,))
    con.execute("UPDATE lessons SET status='retired' WHERE id=?", (a.id,))
    con.commit()
    print(f"lesson #{a.id} retired")


def cmd_add_gap(a) -> None:
    con = connect()
    cur = con.execute(
        "INSERT INTO gaps(date,title,detail,source,priority) "
        "VALUES (?,?,?,?,?)",
        (today(), a.title, a.detail, a.source, a.priority))
    con.commit()
    print(f"gap #{cur.lastrowid} added (P{a.priority}, {a.source})")


def _set_gap(gap_id: int, status: str) -> None:
    con = connect()
    one(con, "SELECT id FROM gaps WHERE id=?", (gap_id,))
    closed = today() if status in ("done", "wontfix") else None
    con.execute("UPDATE gaps SET status=?, closed_date=? WHERE id=?",
                (status, closed, gap_id))
    con.commit()
    print(f"gap #{gap_id} -> {status}" +
          (f" ({closed})" if closed else ""))


def cmd_start_gap(a) -> None:
    _set_gap(a.id, "in_progress")


def cmd_done_gap(a) -> None:
    _set_gap(a.id, "done")


def cmd_drop_gap(a) -> None:
    _set_gap(a.id, "wontfix")


def cmd_decide(a) -> None:
    con = connect()
    cur = con.execute(
        "INSERT INTO decisions(date,what,why,rejected) VALUES (?,?,?,?)",
        (today(), a.what, a.why, a.rejected))
    con.commit()
    print(f"decision #{cur.lastrowid} recorded")


def cmd_log_day(a) -> None:
    con = connect()
    cur = con.execute(
        "INSERT INTO daily_log(date,done,next) VALUES (?,?,?)",
        (today(), a.done, a.next))
    con.commit()
    print(f"day #{cur.lastrowid} logged ({today()}) — receipt saved")


def cmd_export(a) -> None:
    con = connect()
    data = {t: [dict(r) for r in con.execute(f"SELECT * FROM {t}")]
            for t in ("lessons", "gaps", "decisions", "daily_log")}
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"exported -> {a.out}")
    else:
        print(text)


# ---------------------------------------------------------------- selfcheck
def cmd_selfcheck(_args) -> None:
    """Ponytail: ONE runnable check, no frameworks. Assert-based, temp DB."""
    tmp = tempfile.mkdtemp(prefix="parwa_ll_check_")
    os.environ["PARWA_LEARNING_DB"] = os.path.join(tmp, "check.db")
    checks = []

    def ok(name, fn):
        fn()
        checks.append(name)

    def run(*argv):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            main(list(argv))

    ok("briefing on empty db", lambda: run("briefing"))
    ok("seed inserts", lambda: run("seed"))
    ok("seed is one-time", lambda: run("seed"))
    ok("add-lesson with quotes+unicode", lambda: run(
        "add-lesson", "crash on client's \"special\" 数据 — quotes 'x'",
        "--rule", "parameterized SQL only, never f-string a query",
        "--cat", "design", "--root", "string-built SQL"))
    ok("hit-lesson bumps count", lambda: run("hit-lesson", "1"))
    ok("retire-lesson", lambda: run("retire-lesson", "1"))
    ok("add-gap defaults P2/discussion", lambda: run("add-gap", "test gap"))
    ok("start-gap", lambda: run("start-gap", "9"))
    ok("done-gap closes with date", lambda: run("done-gap", "9"))
    ok("add + drop-gap -> wontfix", lambda: (
        run("add-gap", "drop me"), run("drop-gap", "10")))
    ok("invalid gap id exits 1", lambda: _expect_exit(
        1, lambda: run("start-gap", "999")))
    ok("decide", lambda: run(
        "decide", "--what", "test decision", "--why", "because",
        "--rejected", "alternative"))
    ok("log-day", lambda: run(
        "log-day", "--done", "test day", "--next", "tomorrow"))
    ok("missing required arg exits 2", lambda: _expect_exit(
        2, lambda: run("add-lesson", "no rule given")))

    con = sqlite3.connect(db_path())
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("lessons", "gaps", "decisions", "daily_log")}
    assert counts == {"lessons": 8, "gaps": 10, "decisions": 4,
                      "daily_log": 2}, counts
    checks.append("SELECT COUNT verification (learned rule #1)")

    les = con.execute(
        "SELECT times_hit, status FROM lessons WHERE id=1").fetchone()
    assert les[0] == 3 and les[1] == "retired", les  # seeded x2 + hit-lesson
    gap = con.execute(
        "SELECT status, closed_date FROM gaps WHERE id=9").fetchone()
    assert gap[0] == "done" and gap[1] is not None, gap
    gap10 = con.execute(
        "SELECT status FROM gaps WHERE id=10").fetchone()
    assert gap10[0] == "wontfix", gap10
    checks.append("row-level state checks")

    con.execute("INSERT INTO lessons(date,category,symptom,rule) "
                "VALUES (?,?,?,?)",
                (today(), "bug", "unicode café ✓ 数据", "rule 'quoted' \"ok\""))
    row = con.execute(
        "SELECT symptom, rule FROM lessons ORDER BY id DESC LIMIT 1").fetchone()
    assert row[0] == "unicode café ✓ 数据" and "quoted" in row[1], row
    checks.append("unicode + quotes roundtrip")

    for c in checks:
        print(f"  PASS {c}")
    print(f"SELFCHECK: {len(checks)}/{len(checks)} PASS (temp db: {tmp})")


def _expect_exit(code: int, fn) -> None:
    try:
        fn()
    except SystemExit as e:
        assert e.code == code, f"exit {e.code} != {code}"
        return
    raise AssertionError(f"expected SystemExit({code}), none raised")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        prog="learning_loop", description="PARWA daily-improvement memory")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create tables (idempotent)")
    s.set_defaults(func=cmd_init)
    s = sub.add_parser("seed", help="one-time real-history seed")
    s.set_defaults(func=cmd_seed)
    s = sub.add_parser("briefing", help="today's briefing")
    s.add_argument("--rules-limit", type=int, default=8)
    s.set_defaults(func=cmd_briefing)

    s = sub.add_parser("add-lesson", help="record a mistake -> rule")
    s.add_argument("symptom")
    s.add_argument("--rule", required=True)
    s.add_argument("--cat", default="bug",
                   choices=["bug", "design", "process", "testing"])
    s.add_argument("--root", default="")
    s.add_argument("--hits", type=int, default=1)
    s.set_defaults(func=cmd_add_lesson)

    s = sub.add_parser("hit-lesson", help="rule saved us again: bump count")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_hit_lesson)

    s = sub.add_parser("retire-lesson", help="rule got old: retire it")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_retire_lesson)

    s = sub.add_parser("add-gap", help="record a missing part / bug / idea")
    s.add_argument("title")
    s.add_argument("--detail", default="")
    s.add_argument("--priority", type=int, default=2, choices=[1, 2, 3])
    s.add_argument("--source", default="discussion",
                   choices=["discussion", "ticket", "ui_test", "prod"])
    s.set_defaults(func=cmd_add_gap)

    for name, fn in (("start-gap", cmd_start_gap), ("done-gap", cmd_done_gap),
                     ("drop-gap", cmd_drop_gap)):
        s = sub.add_parser(name)
        s.add_argument("id", type=int)
        s.set_defaults(func=fn)

    s = sub.add_parser("decide", help="record a decision + why")
    s.add_argument("--what", required=True)
    s.add_argument("--why", default="")
    s.add_argument("--rejected", default="")
    s.set_defaults(func=cmd_decide)

    s = sub.add_parser("log-day", help="today's receipt (never skip)")
    s.add_argument("--done", required=True)
    s.add_argument("--next", default="")
    s.set_defaults(func=cmd_log_day)

    s = sub.add_parser("export", help="dump all tables as JSON")
    s.add_argument("--out", default=None)
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("selfcheck", help="run the built-in check")
    s.set_defaults(func=cmd_selfcheck)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
