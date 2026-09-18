"""
Space Worker Entrypoint — runs the SAME 8-node PARWA pipeline workers
on a z.ai space box instead of inside Render.

WHY THIS EXISTS
Render free tier has 512MB RAM. Each concurrent pipeline costs ~45MB,
so Render can hold 3 lanes (MAX_CONCURRENT_PIPELINES=3, unchanged here).
This process claims tickets from the SAME database queue
(tickets.status='open') using the SAME _start_pipeline_workers() code
from pipeline_dispatcher, so Render's 3 lanes and this box's lanes
share one queue safely (SELECT ... FOR UPDATE SKIP LOCKED = no double
claims). Total lanes = 3 (Render) + SPACE_CONCURRENCY (this box).

SAFETY GUARD (runs on EVERY start):
Refuses to boot unless the database user is the limited "variant_agent"
user created by database/sql/variant_agent_user.sql. Checks:
  1. Not a PostgreSQL superuser
  2. Cannot SELECT from users / subscriptions (no billing/auth access)
  3. Cannot DELETE from tickets (queue integrity)
If any check passes when it must fail, the worker exits loudly.

USAGE (from the backend/ directory):
  python run_space_worker.py             # run forever
  python run_space_worker.py --preflight # safety checks only, then exit

ENV (see docs/SPACE_WORKER_SETUP.md):
  DATABASE_URL          limited user's connection string (sslmode enforced)
  SPACE_CONCURRENCY     lanes on this box (default 2)
  SPACE_WORKER_ID       unique id for the heartbeat row (default host-pid)
  LLM keys              same env keys as Render (Groq/Mistral/NVIDIA)
"""

from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time

POLL_INTERVAL_SECONDS = 30          # heartbeat cadence
FAKE_TICKET_ID = "00000000-0000-0000-0000-000000000000"  # probe target
_STARTED_AT = time.time()            # for the health endpoint uptime


def _start_health_server(worker_id: str) -> None:
    """Tiny HTTP health endpoint so the space box has a live URL.

    Spaces expect a service with a port — this answers GET / and /health
    with the worker's live status (stdlib only, no new dependency).
    Disable with SPACE_HEALTH_PORT=0.
    """
    port = int(os.environ.get("SPACE_HEALTH_PORT", "8080"))
    if port <= 0:
        return

    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _health_payload(worker_id)
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_a):
            pass  # keep the worker log clean

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
        threading.Thread(
            target=server.serve_forever, daemon=True,
            name="space-worker-health",
        ).start()
        _log(f"health endpoint live on port {port} (GET /health)")
    except OSError as exc:
        _log(f"health_endpoint_failed port={port}: {exc} — worker continues")


def _health_payload(worker_id: str) -> str:
    """One-line JSON status. Never raises (BC-008 style)."""
    import json as _json
    lanes = os.environ.get("SPACE_CONCURRENCY", "2")
    in_progress = -1
    try:
        from sqlalchemy import text as _text
        from database.base import SessionLocal as _SL
        db = _SL()
        try:
            in_progress = int(db.execute(_text(
                "SELECT COUNT(*) FROM tickets WHERE status = 'processing'"
            )).scalar() or 0)
        finally:
            db.close()
    except Exception:
        pass
    return _json.dumps({
        "status": "running",
        "service": "parwa-space-worker",
        "worker_id": worker_id,
        "lanes": lanes,
        "tickets_in_progress": in_progress,
        "uptime_seconds": int(time.time() - _STARTED_AT),
        "version": os.environ.get("RENDER_GIT_COMMIT", "dev")[:7],
    })


def _log(msg: str) -> None:
    print(f"[space-worker] {msg}", flush=True)


def _is_sqlite() -> bool:
    """Local/test runs use SQLite — guard's PG probes don't apply."""
    from database.base import _db_url
    return _db_url.startswith("sqlite")


def _assert_restricted_db_user() -> None:
    """Refuse to start unless the DB user is properly limited.

    Every probe expects FAILURE. A probe that unexpectedly SUCCEEDS means
    the grants are wrong → hard exit before a single ticket is claimed.
    """
    if _is_sqlite():
        _log("WARNING: SQLite detected — restriction probes skipped (test mode only)")
        return

    from sqlalchemy import text
    from database.base import SessionLocal

    db = SessionLocal()
    violations: list[str] = []
    try:
        current_user = db.execute(text("SELECT current_user")).scalar()
        _log(f"connected as db_user={current_user}")

        # Probe 1: must NOT be superuser
        is_super = db.execute(text(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        )).scalar()
        if is_super:
            violations.append(f"user '{current_user}' is a SUPERUSER")

        # Probe 2: must NOT read auth/billing tables
        for table in ("users", "subscriptions"):
            try:
                db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                db.rollback()
                violations.append(f"user can SELECT from '{table}'")
            except Exception:
                db.rollback()  # expected: permission denied

        # Probe 3: must NOT delete tickets (queue integrity)
        try:
            db.execute(text("BEGIN"))
            db.execute(text(
                f"DELETE FROM tickets WHERE id = '{FAKE_TICKET_ID}'"
            ))
            violations.append("user can DELETE from 'tickets'")
        except Exception:
            pass  # expected: permission denied
        finally:
            db.rollback()
    finally:
        db.close()

    if violations:
        for v in violations:
            _log(f"SECURITY VIOLATION: {v}")
        _log("REFUSING TO START. Apply database/sql/variant_agent_user.sql "
             "and use ONLY the variant_agent user's connection string.")
        sys.exit(78)  # EX_CONFIG: misconfiguration
    _log("safety guard passed: db user is properly limited")


def _heartbeat_loop(stop_event: threading.Event, worker_id: str) -> None:
    """Upsert a liveness row every POLL_INTERVAL_SECONDS for Jarvis Domain 12."""
    from sqlalchemy import text
    from database.base import SessionLocal

    hostname = socket.gethostname()
    concurrency = int(os.environ.get("SPACE_CONCURRENCY", "2"))
    version = os.environ.get("RENDER_GIT_COMMIT", "dev")[:7]

    while not stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                in_progress = db.execute(text(
                    "SELECT COUNT(*) FROM tickets WHERE status = 'processing'"
                )).scalar()
                db.execute(text(
                    "INSERT INTO space_worker_heartbeat "
                    "(worker_id, hostname, concurrency, status, "
                    " tickets_in_progress, started_at, last_beat_at, version) "
                    "VALUES (:wid, :host, :cc, 'running', :tip, NOW(), NOW(), :ver) "
                    "ON CONFLICT (worker_id) DO UPDATE SET "
                    "hostname = EXCLUDED.hostname, "
                    "concurrency = EXCLUDED.concurrency, "
                    "status = 'running', "
                    "tickets_in_progress = EXCLUDED.tickets_in_progress, "
                    "last_beat_at = NOW(), version = EXCLUDED.version"
                ), {
                    "wid": worker_id, "host": hostname, "cc": concurrency,
                    "tip": int(in_progress or 0), "ver": version,
                })
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            _log(f"heartbeat_failed: {str(exc)[:200]} — did you run "
                 "database/sql/variant_agent_user.sql as the master user?")
        stop_event.wait(POLL_INTERVAL_SECONDS)


def _mark_stopped(worker_id: str) -> None:
    """Best-effort: tell Jarvis this lane set is going away."""
    try:
        from sqlalchemy import text
        from database.base import SessionLocal
        if _is_sqlite():
            return
        db = SessionLocal()
        try:
            db.execute(text(
                "UPDATE space_worker_heartbeat SET status = 'stopped', "
                "last_beat_at = NOW() WHERE worker_id = :wid"
            ), {"wid": worker_id})
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def main() -> None:
    preflight_only = "--preflight" in sys.argv
    space_concurrency = int(os.environ.get("SPACE_CONCURRENCY", "2"))
    worker_id = os.environ.get(
        "SPACE_WORKER_ID", f"{socket.gethostname()}-{os.getpid()}"
    )

    # pipeline_dispatcher reads MAX_CONCURRENT_PIPELINES at import time —
    # set it BEFORE that import so the space box gets its own lane count.
    os.environ["MAX_CONCURRENT_PIPELINES"] = str(space_concurrency)

    _log(f"starting preflight worker_id={worker_id} lanes={space_concurrency}")
    _assert_restricted_db_user()

    # Prove the real worker code imports cleanly BEFORE going live.
    from app.services.pipeline_dispatcher import _start_pipeline_workers  # noqa: F401
    _log("preflight passed: worker code imports OK")

    if preflight_only:
        _log("preflight-only mode: exiting 0 (no workers started)")
        return

    # ── Go live: claim loop + heartbeat ────────────────────────────
    stop_event = threading.Event()

    def _on_signal(signum, _frame):
        _log(f"signal {signum} received — stopping gracefully")
        stop_event.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    heartbeat = threading.Thread(
        target=_heartbeat_loop, args=(stop_event, worker_id),
        daemon=True, name="space-worker-heartbeat",
    )
    heartbeat.start()

    _start_health_server(worker_id)
    _start_pipeline_workers()
    _log(f"space worker live: lanes={space_concurrency} "
         f"heartbeat_every={POLL_INTERVAL_SECONDS}s — Ctrl+C to stop")

    while not stop_event.is_set():
        time.sleep(1)

    _mark_stopped(worker_id)
    _log("stopped. Render's lanes keep solving tickets on their own.")


if __name__ == "__main__":
    main()
