"""
LLM speed fixes — runnable checks behind the 2026-09-18 live-log findings.

Render logs (2026-09-18 08:35Z) showed the real cause of 4.5-minute
tickets:
  - "NVIDIA timeout on call #2 (attempt 3/3) — waiting 60s, then retrying"
    repeatedly → one node blocked for minutes
  - "llm_queue_recovery: found 10 stuck requests" every 30s — the
    recovery loop had NO time filter, so HEALTHY in-flight rows were
    re-flagged stuck and re-fired → duplicate calls → 429 storm
  - "llm_queue_recovery_retry_exception: request=... err=" (empty) —
    httpx.TimeoutException str() is empty

Covers:
  1. UNIT       _order_backbone_candidates: NVIDIA is ALWAYS last (even
                with the most remaining RPM); disabled providers removed;
                fast providers water-fill by remaining RPM.
  2. INTEGRATION _recover_stuck_llm_requests against a REAL sqlite
                llm_request_queue table: fresh in-flight rows are NOT
                touched, genuinely stale rows fire exactly ONCE even when
                the recovery loop runs twice while a re-fire is still
                running, and rows of unknown providers are drained.
                Runs in a subprocess because tests/conftest.py mocks
                database.models globally (house style).
  3. UNIT       _call_nvidia_direct: timeout → fast-fail (NO 60s sleep,
                single HTTP attempt, raises immediately).
  4. UNIT       _call_nvidia_direct: 429 → at most 2 short (15s) waits,
                then raises — no 3×60s stall.
  5. UNIT       _retry_single_llm_request logs the exception TYPE (no
                more empty "err=").

Run: cd backend && ../venv/bin/python -m pytest tests/test_llm_speed_fixes.py -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_py(code: str, extra_env: dict | None = None, timeout: int = 120) -> str:
    """Run python in a clean subprocess from the backend dir.

    2026-09-18: DATABASE_URL is HARD-SET (not setdefault) to a UNIQUE fresh
    sqlite file per run — the shell/tooling env can carry a pre-set
    DATABASE_URL (z.ai template dev db), and recovery tests must never
    read or write a foreign database.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///./test_llm_speed_{uuid.uuid4().hex[:8]}.db"
    env.pop("NVIDIA_API_KEY", None)  # tests set their own
    if extra_env:
        env.update(extra_env)
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR), env=env,
        capture_output=True, text=True, timeout=timeout,
    )
    assert out.returncode == 0, f"subprocess failed:\n{out.stderr[-1200:]}"
    return out.stdout.strip()


# ── 1: NVIDIA is strictly the last-resort candidate ──────────────────────

ORDER_TEST_CODE = r"""
import app.core.parwa_pipeline.llm_client as lc

cands = [("groq", "f_groq"), ("mistral", "f_mistral"), ("nvidia", "f_nvidia")]

# Force-enable everything and control the RPM windows directly.
lc._provider_disabled = lambda name: False
lc._rpm_remaining = lambda name: {"groq": 1, "mistral": 2, "nvidia": 99}[name]
order = [n for n, _ in lc._order_backbone_candidates(cands)]
assert order == ["mistral", "groq", "nvidia"], (
    f"nvidia must be LAST even with the most remaining RPM, got {order}"
)

# Fresh NVIDIA window outranking Groq was the live bug — repeat it exactly:
lc._rpm_remaining = lambda name: {"groq": 0, "mistral": 0, "nvidia": 40}[name]
order2 = [n for n, _ in lc._order_backbone_candidates(cands)]
assert order2[-1] == "nvidia", f"nvidia still must be last, got {order2}"

# Disabled providers are removed entirely (RPM limit = 0 env case).
lc._provider_disabled = lambda name: name in ("mistral", "nvidia")
lc._rpm_remaining = lambda name: {"groq": 5, "mistral": 9, "nvidia": 9}[name]
order3 = [n for n, _ in lc._order_backbone_candidates(cands)]
assert order3 == ["groq"], f"disabled providers must be removed, got {order3}"

print("ORDER_OK")
"""


def test_nvidia_is_strict_last_resort_in_backbone_ordering():
    out = _run_py(ORDER_TEST_CODE)
    assert "ORDER_OK" in out


# ── 2: recovery loop time filter + in-flight guard (real sqlite) ────────

RECOVERY_TEST_CODE = r"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

# HARD-SET (never setdefault) — the parent env may carry a foreign
# DATABASE_URL; this test must own its database.
os.environ["DATABASE_URL"] = "sqlite:///./test_llm_recovery_" + uuid.uuid4().hex[:8] + ".db"

import app.core.parwa_pipeline.llm_client as lc
from database.base import SessionLocal
from database.models.core import LLMRequestQueue

engine = None
from database.base import engine as _engine
try:
    LLMRequestQueue.__table__.create(_engine)  # tolerate import-chain create_all
except Exception as e:
    if "already exists" not in str(e):
        raise

now = datetime.now(timezone.utc)
stale = now - timedelta(minutes=6)

rows = {
    # fresh in-flight call — must NOT be touched (the live bug)
    "fresh_inprog": dict(status="in_progress", created_at=now, provider="nvidia"),
    # genuinely stale (Render died mid-call) — must fire ONCE
    "stale_inprog": dict(status="in_progress", created_at=stale, provider="nvidia"),
    # 429 wait not yet due — must NOT be touched
    "future_rl": dict(status="rate_limited", created_at=stale, provider="nvidia",
                      next_retry_at=now + timedelta(seconds=60), retry_count=1),
    # 429 wait expired — must fire
    "due_rl": dict(status="rate_limited", created_at=stale, provider="nvidia",
                   next_retry_at=now - timedelta(seconds=1), retry_count=1),
    # unknown provider — must be drained (marked failed), never fired
    "wrong_provider": dict(status="in_progress", created_at=stale, provider="groq"),
}

sid = {}
db = SessionLocal()
for key, spec in rows.items():
    rid = str(uuid.uuid4())
    sid[key] = rid
    db.add(LLMRequestQueue(
        id=rid, provider=spec["provider"], model="test-model",
        messages='[{"role":"user","content":"hi"}]',
        temperature=0.1, max_tokens=64, call_id=1,
        status=spec["status"], retry_count=spec.get("retry_count", 0),
        max_retries=2, next_retry_at=spec.get("next_retry_at"),
        created_at=spec["created_at"], updated_at=spec["created_at"],
    ))
db.commit()
db.close()

fired_ids = []
_orig_retry = lc._retry_single_llm_request

async def counting_retry(**kw):
    fired_ids.append(kw["request_id"])
    await _orig_retry(**kw)

lc._retry_single_llm_request = counting_retry

async def fake_nvidia(messages, temperature, max_tokens, call_id):
    await asyncio.sleep(1.5)  # simulate a slow re-fire still running
    return "ok"

lc._call_nvidia_direct = fake_nvidia

async def main():
    # Cycle 1 — fires the stale rows (as background tasks)
    await lc._recover_stuck_llm_requests()
    # Cycle 2 immediately after — re-fires must be blocked by the
    # in-flight guard (first tasks still sleeping) and by row states.
    await lc._recover_stuck_llm_requests()
    await asyncio.sleep(2.5)  # let background tasks finish

asyncio.run(main())

# Per-row assertions — immune to stray rows from any foreign database.
MY_FIRED = set(fired_ids)
MY_FIRED_LIST = list(fired_ids)

db = SessionLocal()
def get(rid):
    return db.query(LLMRequestQueue).filter(LLMRequestQueue.id == rid).first()

# fresh in-flight: untouched and NEVER fired
fresh = get(sid["fresh_inprog"])
assert fresh is not None and fresh.status == "in_progress", "fresh row was touched!"
assert sid["fresh_inprog"] not in MY_FIRED, "fresh row was fired!"

# future rate_limited: untouched and NEVER fired
f_rl = get(sid["future_rl"])
assert f_rl is not None and f_rl.status == "rate_limited", "future 429 row was touched!"
assert sid["future_rl"] not in MY_FIRED, "future 429 row was fired!"

# unknown provider: drained to failed, never fired
wp = get(sid["wrong_provider"])
assert wp is not None and wp.status == "failed", "unknown-provider row not drained!"
assert sid["wrong_provider"] not in MY_FIRED, "unknown-provider row was fired!"

# stale rows: fired EXACTLY ONCE (in-flight guard blocked cycle-2 re-fire),
# then deleted on success.
assert MY_FIRED_LIST.count(sid["stale_inprog"]) == 1, (
    f"stale_inprog fired {MY_FIRED_LIST.count(sid['stale_inprog'])} times — guard leak!"
)
assert MY_FIRED_LIST.count(sid["due_rl"]) == 1, (
    f"due_rl fired {MY_FIRED_LIST.count(sid['due_rl'])} times — guard leak!"
)
assert get(sid["stale_inprog"]) is None, "stale row not deleted after successful retry"
assert get(sid["due_rl"]) is None, "due_rl row not deleted after successful retry"

db.close()
print("RECOVERY_OK")
"""


def test_recovery_loop_time_filter_and_inflight_guard():
    # NVIDIA_RPM=40 so nvidia rows are recoverable (RPM=0 → recovery DRAINS
    # them — that is the dead-key protection, covered by the drain asserts).
    out = _run_py(RECOVERY_TEST_CODE, extra_env={"NVIDIA_RPM": "40"}, timeout=120)
    assert "RECOVERY_OK" in out


# ── 3 + 4: NVIDIA fast-fail (timeout, 429) ───────────────────────────────

NVIDIA_TIMEOUT_CODE = r"""
import asyncio, time
os_unused = None
import os
os.environ["NVIDIA_API_KEY"] = "nvapi-test"

import httpx
import app.core.parwa_pipeline.llm_client as lc

class FakeTimeoutClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, *a, **k):
        raise httpx.ReadTimeout("read timed out")

import httpx as _h
_orig = _h.AsyncClient
_h.AsyncClient = FakeTimeoutClient

attempts = {"n": 0}
_orig_mark = lc._mark_llm_queue_failed
lc._mark_llm_queue_failed = lambda rid, err: attempts.__setitem__("failed", err)

async def main():
    t0 = time.monotonic()
    try:
        await lc._call_nvidia_direct([{"role": "user", "content": "hi"}], 0.1, 64, 1)
        return "NO_RAISE"
    except httpx.TimeoutException:
        elapsed = time.monotonic() - t0
        # OLD behaviour: 60s timeout + 60s wait ×3 → ~6 minutes.
        # NEW behaviour: single attempt, fast-fail → well under 10s.
        assert elapsed < 10, f"timeout fast-fail took {elapsed:.1f}s (should be <10s)"
        return f"FAST_FAIL_OK {elapsed:.2f}s"

print(asyncio.run(main()))
_h.AsyncClient = _orig
"""

NVIDIA_429_CODE = r"""
import asyncio, time, os
os.environ["NVIDIA_API_KEY"] = "nvapi-test"

import httpx
import app.core.parwa_pipeline.llm_client as lc

posts = {"n": 0}

class FakeResp:
    status_code = 429
    text = '{"status":429,"title":"Too Many Requests"}'
    def json(self): return {}

class Fake429Client:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, *a, **k):
        posts["n"] += 1
        return FakeResp()

_h = httpx
_orig = _h.AsyncClient
_h.AsyncClient = Fake429Client

# Make the 15s waits instant for the test — we assert the COUNT of waits.
async def instant_sleep(_s):
    await asyncio.sleep(0)
lc_orig_sleep = asyncio.sleep

attempts = {}
lc._mark_llm_queue_failed = lambda rid, err: attempts.__setitem__("failed", err)

async def main():
    # patch asyncio.sleep ONLY inside the running loop via monkey module attr
    import app.core.parwa_pipeline.llm_client as _lc
    t0 = time.monotonic()
    try:
        await _lc._call_nvidia_direct([{"role": "user", "content": "hi"}], 0.1, 64, 1)
        return "NO_RAISE"
    except RuntimeError as exc:
        elapsed = time.monotonic() - t0
        # 3 attempts (MAX_RETRIES=2 → 2 short waits), no 60s stalls
        assert posts["n"] == 3, f"expected 3 attempts, got {posts['n']}"
        assert "429" in str(exc) or "429" in attempts.get("failed", "")
        return f"RATE_LIMIT_BOUNDED_OK attempts={posts['n']} elapsed={elapsed:.2f}s"

# Replace asyncio.sleep with instant version for THIS run (waits are 15s real;
# we only verify the retry COUNT and that no 60s waits exist).
_real_sleep = asyncio.sleep
async def fast_sleep(delay, *a, **k):
    assert delay <= 15.5, f"sleep too long: {delay}s (60s waits are back!)"
    return await _real_sleep(0)
asyncio.sleep = fast_sleep
result = asyncio.run(main())
asyncio.sleep = _real_sleep
_h.AsyncClient = _orig
print(result)
"""


def test_nvidia_timeout_fails_fast_without_60s_waits():
    out = _run_py(NVIDIA_TIMEOUT_CODE, timeout=60)
    assert "FAST_FAIL_OK" in out


def test_nvidia_429_retries_are_bounded_and_short():
    out = _run_py(NVIDIA_429_CODE, timeout=60)
    assert "RATE_LIMIT_BOUNDED_OK attempts=3" in out


# ── 5: exception type always in recovery error logs ──────────────────────

EMPTY_ERR_CODE = r"""
import asyncio, logging, os
os.environ["NVIDIA_API_KEY"] = "nvapi-test"

import httpx
import app.core.parwa_pipeline.llm_client as lc

records = []
class Grab(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())
logging.getLogger("parwa.pipeline.llm").addHandler(Grab())
logging.getLogger("parwa.pipeline.llm").setLevel(logging.WARNING)

lc._update_llm_queue_status = lambda *a, **k: None
lc._mark_llm_queue_failed = lambda *a, **k: None
lc._delete_llm_queue_row = lambda *a, **k: None

async def boom(*a, **k):
    raise asyncio.TimeoutError()  # str() is EMPTY — exactly the live "err=" case

lc._call_nvidia_direct = boom

async def main():
    await lc._retry_single_llm_request("aaaaaaaa-0000-0000-0000-000000000000", [], 0.1, 64, 1)

asyncio.run(main())
joined = "\n".join(records)
assert "llm_queue_recovery_retry_exception" in joined
assert ("TimeoutError" in joined or "TimeoutException" in joined), (
    f"exception TYPE missing from log: {joined!r}"
)
assert not any(
    line.rstrip().endswith("err=") for line in joined.splitlines()
), f"empty err= still present: {joined!r}"
print("ERR_TYPE_OK")
"""


def test_recovery_logs_exception_type_not_empty_err():
    out = _run_py(EMPTY_ERR_CODE, timeout=60)
    assert "ERR_TYPE_OK" in out


# ── 6: Groq model-rotation self-healing (THE 4.5-min root cause) ─────────

GROQ_FALLBACK_CODE = r"""
import asyncio, os
os.environ["GROQ_API_KEY"] = "gsk_test"
os.environ.pop("GROQ_MODEL", None)

import app.core.parwa_pipeline.llm_client as lc

lc._groq_resolved_model = None  # fresh process state

posts = []

class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = body
    def json(self):
        import json as _j
        return _j.loads(self._body)

NOT_FOUND = '{"error":{"message":"The model `qwen/qwen3.6-27b` does not exist or you do not have access to it.","type":"invalid_request_error","code":"model_not_found"}}'
OK_BODY = '{"choices":[{"message":{"content":"ok answer"}}],"usage":{"total_tokens":5}}'

class FakeGroqClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, json=None, headers=None):
        posts.append(json["model"])
        # First candidate (qwen3.8-27b) is dead — Groq rotated it.
        if json["model"] == "qwen/qwen3.8-27b":
            return FakeResp(404, NOT_FOUND)
        return FakeResp(200, OK_BODY)

import httpx
_orig = httpx.AsyncClient
httpx.AsyncClient = FakeGroqClient

async def main():
    # Call 1: falls through the dead model to the next candidate.
    out = await lc._call_groq_direct([{"role": "user", "content": "hi"}], 0.1, 32, 1)
    assert out == "ok answer", f"unexpected content: {out!r}"
    assert posts == ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"], f"unexpected attempts: {posts}"
    assert lc._groq_resolved_model == "openai/gpt-oss-20b", "winner not cached"

    # Call 2: cached winner is tried FIRST and succeeds — one post only.
    posts.clear()
    out2 = await lc._call_groq_direct([{"role": "user", "content": "hi"}], 0.1, 32, 1)
    assert out2 == "ok answer" and posts == ["openai/gpt-oss-20b"], (
        f"cache miss! posts={posts}"
    )

asyncio.run(main())
httpx.AsyncClient = _orig
print("GROQ_FALLBACK_OK")
"""

GROQ_429_FAST_FAIL_CODE = r"""
import asyncio, os
os.environ["GROQ_API_KEY"] = "gsk_test"
os.environ.pop("GROQ_MODEL", None)

import app.core.parwa_pipeline.llm_client as lc
lc._groq_resolved_model = None

class FakeResp:
    status_code = 429
    text = '{"error":"rate limit exceeded"}'
    def json(self): return {}

class Fake429:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, json=None, headers=None):
        return FakeResp()

import httpx
_orig = httpx.AsyncClient
httpx.AsyncClient = Fake429

async def main():
    try:
        await lc._call_groq_direct([{"role": "user", "content": "hi"}], 0.1, 32, 1)
        return "NO_RAISE"
    except RuntimeError as exc:
        # 429 is NOT a rotation — must raise immediately (no candidate churn),
        # the provider-pool cooldown logic takes over.
        assert "429" in str(exc), str(exc)
        return "RATE_LIMIT_RAISES_OK"

print(asyncio.run(main()))
httpx.AsyncClient = _orig
"""


def test_groq_model_rotation_fallback_and_cache():
    out = _run_py(GROQ_FALLBACK_CODE, timeout=60)
    assert "GROQ_FALLBACK_OK" in out


def test_groq_429_raises_without_candidate_churn():
    out = _run_py(GROQ_429_FAST_FAIL_CODE, timeout=60)
    assert "RATE_LIMIT_RAISES_OK" in out
