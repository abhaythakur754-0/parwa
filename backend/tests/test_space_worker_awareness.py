"""
Runnable check for Jarvis awareness Domain 12 (Space Worker health).

Covers the four states that matter in production:
  absent   → no heartbeat rows ever  → never alert (space is optional)
  healthy  → fresh beat (≤90s)       → never alert, stale=False
  stale    → old beat (>90s)         → alert IS created (deduped)
  db error → collector degrades to absent, never raises (BC-008)

Run: cd backend && python -m pytest tests/test_space_worker_awareness.py -q
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services.jarvis_awareness_engine import (
    _check_space_worker_health,
    _collect_space_worker_health,
)

COMPANY = "company-1"
SESSION = "session-1"
SNAPSHOT = "snapshot-1"


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDB:
    """Minimal db double: only what the Domain 12 code path touches."""

    def __init__(self, rows=None, error=None):
        self._rows = rows or []
        self._error = error

    def execute(self, *_a, **_k):
        if self._error:
            raise self._error
        return _FakeResult(self._rows)

    # create_alert() touches these when the stale rule fires
    def add(self, _obj):
        pass

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, _obj):
        pass

    def query(self, *_a, **_k):
        return MagicMock()


def _row(worker_id, age_seconds, status="running", concurrency=4):
    beat = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return (worker_id, concurrency, status, 2, beat)


def test_absent_never_alerts():
    state = _collect_space_worker_health(_FakeDB(rows=[]), COMPANY)
    assert state["space_worker_status"] == "absent"
    assert state["space_worker_stale"] is True
    assert state["space_worker_capacity"] == 0
    alert = _check_space_worker_health(
        _FakeDB(rows=[]), SESSION, COMPANY, state, SNAPSHOT
    )
    assert alert is None  # never deployed → normal → no alert


def test_healthy_no_alert():
    state = _collect_space_worker_health(
        _FakeDB(rows=[_row("space-1", 10)]), COMPANY
    )
    assert state["space_worker_status"] == "healthy"
    assert state["space_worker_stale"] is False
    assert state["space_worker_count"] == 1
    assert state["space_worker_capacity"] == 4
    alert = _check_space_worker_health(
        _FakeDB(rows=[_row("space-1", 10)]), SESSION, COMPANY, state, SNAPSHOT
    )
    assert alert is None


def test_stale_creates_warning_alert():
    state = _collect_space_worker_health(
        _FakeDB(rows=[_row("space-1", age_seconds=300)]), COMPANY
    )
    assert state["space_worker_status"] == "stale"
    assert state["space_worker_stale"] is True
    alert = _check_space_worker_health(
        _FakeDB(rows=[_row("space-1", age_seconds=300)]),
        SESSION, COMPANY, state, SNAPSHOT,
    )
    assert alert is not None  # previously-seen worker went silent


def test_stopped_status_counts_as_stale():
    state = _collect_space_worker_health(
        _FakeDB(rows=[_row("space-1", 10, status="stopped")]), COMPANY
    )
    assert state["space_worker_status"] == "stale"


def test_db_error_degrades_to_absent():
    state = _collect_space_worker_health(
        _FakeDB(error=RuntimeError("table missing")), COMPANY
    )
    assert state["space_worker_status"] == "absent"  # BC-008: never raises
    assert state["space_worker_count"] == 0
