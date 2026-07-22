"""
Unit tests for billing event emission.

Verifies:
1. `emit_billing_event` exists and is callable (previously ImportError bug)
2. Billing event types are registered in the EventRegistry
3. Short event names ("usage_warning") are auto-prefixed to "billing:usage_warning"
4. Already-prefixed names ("billing:usage_warning") pass through unchanged
5. The renewal reminder task function exists and is importable
6. Celery beat schedule contains the new billing tasks

Per CLAUDE.md Rule #5: "Never say it works unless you have PROVEN it works."
"""

import sys
import os
from pathlib import Path

# Ensure backend/ is on sys.path
# This file is at backend/tests/unit/test_billing_events.py
# _BACKEND should resolve to backend/
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def test_emit_billing_event_exists_and_is_callable():
    """emit_billing_event must exist in app.core.event_emitter and be callable."""
    from app.core.event_emitter import emit_billing_event
    assert callable(emit_billing_event), "emit_billing_event must be callable"


def test_billing_event_types_registered():
    """All 5 billing event types must be registered in the EventRegistry."""
    from app.core.events import get_event_registry, EventCategory

    reg = get_event_registry()
    billing_events = {
        et.type_str for et in reg.get_events_by_category(EventCategory.BILLING)
    }
    expected = {
        "billing:usage_warning",
        "billing:usage_limit_exceeded",
        "billing:renewal_reminder",
        "billing:payment_failed",
        "billing:subscription_updated",
    }
    missing = expected - billing_events
    assert not missing, f"Missing billing event types: {missing}"


def test_billing_event_payload_schema_validates():
    """BillingEventPayload must accept the fields the backend emits."""
    from app.core.events import BillingEventPayload

    payload = BillingEventPayload(
        company_id="comp-1",
        event_subtype="usage_warning",
        usage_percentage=85.5,
        tickets_used=1700,
        ticket_limit=2000,
        variant="growth",
    )
    assert payload.usage_percentage == 85.5
    assert payload.tickets_used == 1700
    assert payload.variant == "growth"


def test_emit_billing_event_short_name_gets_prefixed(monkeypatch):
    """Short event name 'usage_warning' must be prefixed to 'billing:usage_warning'."""
    captured = {}

    async def fake_emit_event(company_id, event_type, payload, correlation_id=None):
        captured["company_id"] = company_id
        captured["event_type"] = event_type
        captured["payload"] = payload
        return True

    # Monkeypatch the module-level emit_event used by emit_billing_event
    from app.core import event_emitter
    monkeypatch.setattr(event_emitter, "emit_event", fake_emit_event)

    import asyncio
    result = asyncio.run(
        event_emitter.emit_billing_event(
            company_id="comp-1",
            event_type="usage_warning",
            data={"usage_percentage": 85.0, "tickets_used": 1700, "ticket_limit": 2000},
        )
    )

    assert result is True
    assert captured["event_type"] == "billing:usage_warning"
    assert captured["company_id"] == "comp-1"
    assert captured["payload"]["usage_percentage"] == 85.0
    assert captured["payload"]["event_subtype"] == "usage_warning"


def test_emit_billing_event_full_name_passes_through(monkeypatch):
    """Already-prefixed 'billing:usage_warning' must NOT be double-prefixed."""
    captured = {}

    async def fake_emit_event(company_id, event_type, payload, correlation_id=None):
        captured["event_type"] = event_type
        return True

    from app.core import event_emitter
    monkeypatch.setattr(event_emitter, "emit_event", fake_emit_event)

    import asyncio
    asyncio.run(
        event_emitter.emit_billing_event(
            company_id="comp-1",
            event_type="billing:renewal_reminder",
            data={"variant": "growth", "renewal_date": "2025-07-01"},
        )
    )

    assert captured["event_type"] == "billing:renewal_reminder"


def test_send_renewal_reminder_task_exists():
    """The renewal-reminder Celery task must be importable from billing_tasks.

    Skipped when celery is not installed (CI sandbox without full backend deps).
    The import path is verified by static analysis (ast.parse) separately.
    """
    try:
        import celery  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("celery not installed in this environment")

    from app.tasks.billing_tasks import (
        send_renewal_reminder,
        check_all_renewal_reminders,
        subscription_check_all,
        check_all_usage_warnings,
    )
    assert callable(send_renewal_reminder)
    assert callable(check_all_renewal_reminders)
    assert callable(subscription_check_all)
    assert callable(check_all_usage_warnings)


def test_celery_beat_schedule_includes_billing_tasks():
    """Celery beat must schedule the new billing tasks.

    Skipped when celery is not installed (CI sandbox without full backend deps).
    The beat schedule entries are verified by static analysis (grep) separately.
    """
    try:
        import celery  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("celery not installed in this environment")

    from app.tasks.celery_app import app as celery_app

    beat = celery_app.conf.beat_schedule
    schedule_keys = set(beat.keys())

    expected_billing_entries = {
        "billing-check-all-usage-warnings-daily-09utc",
        "billing-check-all-renewal-reminders-daily-08utc",
        "billing-subscription-check-all-daily-06utc",
    }
    missing = expected_billing_entries - schedule_keys
    assert not missing, f"Missing Celery beat entries: {missing}"

    # Verify the usage warning is scheduled at 80% threshold
    usage_entry = beat["billing-check-all-usage-warnings-daily-09utc"]
    assert usage_entry["kwargs"]["threshold"] == 80.0

    # Verify renewal reminder is scheduled 7 days before
    renewal_entry = beat["billing-check-all-renewal-reminders-daily-08utc"]
    assert renewal_entry["kwargs"]["days_before"] == 7


def test_billing_tasks_module_parses_syntactically():
    """billing_tasks.py must be syntactically valid Python (static check).

    This is the fallback test that runs even when celery isn't installed,
    ensuring the renewal-reminder task code at least parses cleanly.
    """
    import ast
    billing_tasks_path = _BACKEND / "app" / "tasks" / "billing_tasks.py"
    source = billing_tasks_path.read_text()
    tree = ast.parse(source)

    # Collect all top-level function names
    func_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    expected_funcs = {
        "send_renewal_reminder",
        "check_all_renewal_reminders",
        "subscription_check_all",
        "check_all_usage_warnings",
        "send_usage_warning",
        "subscription_check",
    }
    missing = expected_funcs - func_names
    assert not missing, f"Missing functions in billing_tasks.py: {missing}"


def test_celery_app_beat_schedule_contains_billing_entries():
    """Static-check celery_app.py for the new billing beat schedule entries.

    This is the fallback test that runs even when celery isn't installed.
    """
    celery_app_path = _BACKEND / "app" / "tasks" / "celery_app.py"
    source = celery_app_path.read_text()

    expected_entries = [
        "billing-check-all-usage-warnings-daily-09utc",
        "billing-check-all-renewal-reminders-daily-08utc",
        "billing-subscription-check-all-daily-06utc",
        "check_all_usage_warnings",
        "check_all_renewal_reminders",
        "subscription_check_all",
    ]
    for entry in expected_entries:
        assert entry in source, f"Missing entry in celery_app.py: {entry}"
