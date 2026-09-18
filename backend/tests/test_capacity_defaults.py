"""
Capacity defaults — runnable checks behind the free-tier rollout decision.

Covers (user decision: 4 ticket lanes on free Render, chat capped at 2):
  1. UNIT       pipeline_dispatcher.MAX_CONCURRENT_PIPELINES defaults to 4
                when the env var is NOT set (code-level default).
  2. UNIT       env var still wins (MAX_CONCURRENT_PIPELINES=7 -> 7, =3 -> 3),
                so an OOM rollback is one env change, no redeploy.
  3. UNIT       Jarvis chat cap MAX_CONCURRENT_JARVIS defaults to 2 in BOTH
                paths (API semaphore + queue worker threads) — the "cheap
                fix" that keeps chats from eating Render RAM.
  4. INTEGRATION the jarvis queue worker claims pending messages from a REAL
                (sqlite) jarvis_message_queue table with the REAL worker
                loop, calls send_message, marks completed, and never exceeds
                the worker-count concurrency. Runs in a subprocess because
                tests/conftest.py mocks database.models globally (house
                style) — this test needs the real ORM model.
  5. WIRING     start_jarvis_queue_workers() spawns exactly
                MAX_CONCURRENT_JARVIS threads and the start guard is
                idempotent (second call spawns nothing).

Run: cd backend && ../venv/bin/python -m pytest tests/test_capacity_defaults.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_py(code: str, extra_env: dict | None = None) -> str:
    """Run python in a clean subprocess from the backend dir (import-time
    env must be controlled from outside the process — module-level reads)."""
    env = dict(os.environ)
    env.pop("MAX_CONCURRENT_PIPELINES", None)
    env.pop("MAX_CONCURRENT_JARVIS", None)
    env.setdefault("DATABASE_URL", "sqlite:///./test_capacity_tmp.db")
    if extra_env:
        env.update(extra_env)
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR), env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, f"subprocess failed:\n{out.stderr[-800:]}"
    return out.stdout.strip()


# ── 1 + 2: ticket lane default & env override ────────────────────────────

def test_ticket_lanes_default_is_4_in_code():
    out = _run_py(
        "import app.services.pipeline_dispatcher as p; print(p.MAX_CONCURRENT_PIPELINES)"
    )
    assert out == "4"


@pytest.mark.parametrize("env_value,expected", [("7", "7"), ("3", "3")])
def test_ticket_lanes_env_var_still_wins(env_value, expected):
    out = _run_py(
        "import app.services.pipeline_dispatcher as p; print(p.MAX_CONCURRENT_PIPELINES)",
        extra_env={"MAX_CONCURRENT_PIPELINES": env_value},
    )
    assert out == expected


# ── 3: jarvis chat cap defaults (both paths agree) ───────────────────────

def test_jarvis_chat_cap_default_is_2_both_paths():
    out = _run_py(
        "import app.services.jarvis_queue_worker as w\n"
        "import app.api.jarvis as api\n"
        "print(w.MAX_CONCURRENT_JARVIS, api.MAX_CONCURRENT_JARVIS, api._JARVIS_SEMAPHORE._value)"
    )
    worker_cap, api_cap, sem_value = out.split()
    assert worker_cap == "2" and api_cap == "2" and sem_value == "2"


# ── 4: integration — REAL worker loop over a REAL sqlite queue ───────────

_INTEGRATION_SCRIPT = r'''
import asyncio, json, sys, threading, time
from datetime import datetime
from types import SimpleNamespace

CURRENT = 0
MAXI = 0

async def fake_send_message(*, db, session_id, user_id, user_message):
    global CURRENT, MAXI
    CURRENT += 1
    MAXI = max(MAXI, CURRENT)
    await asyncio.sleep(0.03)
    CURRENT -= 1
    return (SimpleNamespace(content=user_message),
            SimpleNamespace(content="ai reply", metadata_json=None), [])

# Stub the LLM + session lookup BEFORE the worker imports them at runtime.
# (_process_message imports send_message AND _parse_context.)
sys.modules["app.services.jarvis_service"] = SimpleNamespace(
    get_session=lambda *a, **k: None)
sys.modules["app.services.jarvis.chat"] = SimpleNamespace(
    send_message=fake_send_message,
    _parse_context=lambda *a, **k: {})

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.services.jarvis_queue_worker as jqw
from database.models.jarvis import JarvisMessageQueue

engine = create_engine("sqlite:///./test_jq_integration.db")
JarvisMessageQueue.__table__.drop(engine, checkfirst=True)
JarvisMessageQueue.__table__.create(engine)
maker = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# The worker does `from database.base import SessionLocal` at runtime —
# point that import at our sqlite sessionmaker.
import database.base as real_db_base
real_db_base.SessionLocal = maker

base = time.time()
with maker() as s:
    for i in range(5):
        s.add(JarvisMessageQueue(
            user_id="user-1", session_id="sess-1",
            message_content=f"hello {i}", status="pending",
            queued_at=datetime.utcfromtimestamp(base + i)))
    s.commit()

class StopLoop(Exception):
    pass

class FakeTime:
    def sleep(self, _seconds):
        raise StopLoop()

jqw.time = FakeTime()  # no pending rows -> sleep -> StopLoop -> thread ends

t = threading.Thread(target=jqw._worker_loop, args=(0,), daemon=True,
                     name="integration-jarvis-worker-0")
t.start()
t.join(timeout=30)
terminated = not t.is_alive()

with maker() as s:
    statuses = [r.status for r in s.query(JarvisMessageQueue).all()]

print(json.dumps({
    "terminated": terminated,
    "statuses": statuses,
    "max_inflight": MAXI,
}))
'''


def test_queue_worker_claims_processes_and_respects_concurrency():
    env = dict(os.environ)
    env.pop("MAX_CONCURRENT_JARVIS", None)
    env["DATABASE_URL"] = "sqlite:///./test_jq_integration.db"
    out = subprocess.run(
        [sys.executable, "-c", _INTEGRATION_SCRIPT],
        cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True, timeout=120,
    )
    try:
        data = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:
        pytest.fail(f"no JSON from subprocess. stderr:\n{out.stderr[-800:]}")
    finally:
        (BACKEND_DIR / "test_jq_integration.db").unlink(missing_ok=True)

    assert data["terminated"], "worker thread did not terminate"
    assert data["statuses"].count("completed") == 5, f"statuses={data['statuses']}"
    assert data["statuses"].count("pending") == 0, f"statuses={data['statuses']}"
    assert data["statuses"].count("failed") == 0, f"statuses={data['statuses']}"
    # 1 worker thread -> at most 1 message in flight at any instant.
    assert data["max_inflight"] == 1


# ── 5: wiring — spawn count matches the cap; start guard is idempotent ───

def test_start_jarvis_queue_workers_spawns_cap_threads_and_is_idempotent():
    import app.services.jarvis_queue_worker as jqw

    spawned = []
    real_thread = threading.Thread

    def counting_thread(*args, **kwargs):
        kwargs["target"] = lambda *a, **k: None  # exits immediately
        t = real_thread(*args, **kwargs)
        spawned.append(t)
        return t

    jqw._workers_started = False
    fake_threading = SimpleNamespace(Thread=counting_thread)
    with patch.object(jqw, "_worker_loop", lambda wid: None), \
         patch.object(jqw, "MAX_CONCURRENT_JARVIS", 2), \
         patch.object(jqw, "threading", fake_threading):
        jqw.start_jarvis_queue_workers()
        jqw.start_jarvis_queue_workers()  # guard: second call is a no-op

    assert len(spawned) == 2, f"expected 2 spawns, got {len(spawned)}"
    for t in spawned:
        t.join(timeout=5)
