"""Unit tests: escalation → owner notification bridge.

Covers backend/app/services/escalation_notify.py — the leg that conveys
variant escalation asks to the owner through the standard notification
system (in-app bell + email).

Contract under test:
  1. Dispatches once with the structured ask (problem/needed/after).
  2. Idempotent — a second call for the same escalation is a no-op.
  3. Never raises (BC-008) — service failures are swallowed.
  4. "No human agents" response does NOT mark the ticket as notified.
  5. Falls back to the raw reason when no ask exists in metadata.
  6. Wiring: pipeline_dispatcher calls the bridge on all escalation paths.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.escalation_notify import (  # noqa: E402
    METADATA_KEY,
    build_owner_summary,
    notify_owner_of_escalation,
)

SERVICE_PATH = "app.services.notification_service.NotificationService"

ASK = {
    "escalation_type": "missing_connection",
    "problem": "Cannot process the refund",
    "needed_from_team": "Connect a payment gateway (Razorpay/Stripe/PayPal)",
    "after_that": "The waiting ticket is retried automatically",
}


def make_ask_metadata() -> str:
    return json.dumps({"escalation_ask": ASK, "escalation_reason": "missing_connection"})


class FakeTicket:
    def __init__(self, metadata_json=None):
        self.id = "tik-1234-5678"
        self.company_id = "co-abc-123"
        self.subject = "Refund not received"
        self.customer_id = "cus-1"
        self.priority = "high"
        self.category = "billing"
        self.metadata_json = metadata_json


def _mock_service(response):
    svc = MagicMock()
    svc.notify_human_queue = MagicMock(return_value=response)
    return svc


def _patched(response):
    return patch(SERVICE_PATH, return_value=_mock_service(response))


class TestOwnerSummary(unittest.TestCase):
    def test_summary_contains_all_ask_fields(self):
        summary, esc_reason = build_owner_summary(
            {"escalation_ask": ASK}, reason="", extra_summary="ctx",
        )
        self.assertIn("Problem: Cannot process the refund", summary)
        self.assertIn("Needed from team: Connect a payment gateway", summary)
        self.assertIn("After that: The waiting ticket is retried", summary)
        self.assertIn("ctx", summary)
        self.assertEqual(esc_reason, "missing_connection")

    def test_reason_fallback_without_ask(self):
        summary, esc_reason = build_owner_summary({}, reason="technical_error")
        self.assertIn("Problem: technical_error", summary)
        self.assertEqual(esc_reason, "technical_error")

    def test_corrupt_metadata_is_tolerated(self):
        summary, esc_reason = build_owner_summary(
            {"escalation_ask": "not-a-dict"}, reason="low_confidence",
        )
        self.assertIn("Problem: low_confidence", summary)
        self.assertEqual(esc_reason, "low_confidence")


class TestNotifyOwnerOfEscalation(unittest.TestCase):
    def test_dispatches_once_and_marks_ticket(self):
        ticket = FakeTicket(metadata_json=make_ask_metadata())
        db = MagicMock()
        with _patched({"success": True}) as ctor:
            result = notify_owner_of_escalation(db, ticket, reason="missing_connection")

        self.assertTrue(result["dispatched"])
        ctor.assert_called_once_with(db, "co-abc-123")
        svc = ctor.return_value
        self.assertEqual(svc.notify_human_queue.call_count, 1)
        kwargs = svc.notify_human_queue.call_args.kwargs
        self.assertEqual(kwargs["ticket_id"], "tik-1234-5678")
        self.assertEqual(kwargs["escalation_reason"], "missing_connection")
        self.assertIn("Needed from team", kwargs["summary"])

        stamped = json.loads(ticket.metadata_json)
        self.assertIn(METADATA_KEY, stamped)

    def test_idempotent_second_call_is_noop(self):
        ticket = FakeTicket(metadata_json=make_ask_metadata())
        with _patched({"success": True}) as ctor:
            notify_owner_of_escalation(MagicMock(), ticket)
            result = notify_owner_of_escalation(MagicMock(), ticket)

        self.assertFalse(result["dispatched"])
        self.assertEqual(result["detail"], "already notified")
        self.assertEqual(ctor.return_value.notify_human_queue.call_count, 1)

    def test_service_exception_never_raises(self):
        ticket = FakeTicket(metadata_json=make_ask_metadata())
        svc = MagicMock()
        svc.notify_human_queue = MagicMock(side_effect=RuntimeError("smtp down"))
        with patch(SERVICE_PATH, return_value=svc):
            result = notify_owner_of_escalation(MagicMock(), ticket)

        self.assertFalse(result["dispatched"])
        self.assertIn("smtp down", result["detail"])

    def test_no_agents_leaves_ticket_unmarked(self):
        ticket = FakeTicket(metadata_json=make_ask_metadata())
        with _patched({"success": False, "error": "No human agents available"}):
            result = notify_owner_of_escalation(MagicMock(), ticket)

        self.assertFalse(result["dispatched"])
        self.assertIn("No human agents", result["detail"])
        stamped = json.loads(ticket.metadata_json)
        self.assertNotIn(METADATA_KEY, stamped)

    def test_missing_ticket_identity_is_safe(self):
        ticket = FakeTicket()
        ticket.id = ""
        result = notify_owner_of_escalation(MagicMock(), ticket)
        self.assertFalse(result["dispatched"])

    def test_corrupt_json_never_raises(self):
        ticket = FakeTicket(metadata_json="{not json")
        with _patched({"success": True}):
            result = notify_owner_of_escalation(MagicMock(), ticket, reason="technical_error")
        self.assertTrue(result["dispatched"])


class TestDispatcherWiring(unittest.TestCase):
    def test_pipeline_dispatcher_calls_bridge_on_all_escalation_paths(self):
        dispatcher = (
            Path(__file__).resolve().parents[2]
            / "backend" / "app" / "services" / "pipeline_dispatcher.py"
        )
        source = dispatcher.read_text(encoding="utf-8")
        # 1 import + 3 call sites (2 interrupts + 1 vault)
        self.assertGreaterEqual(source.count("notify_owner_of_escalation"), 4)
        self.assertIn("from app.services.escalation_notify import", source)

    def test_ci_no_longer_references_jarvis_cli(self):
        repo = Path(__file__).resolve().parents[2]
        ci = repo / ".github" / "workflows" / "ci.yml"
        self.assertNotIn("jarvis-cli", ci.read_text(encoding="utf-8"))
        self.assertFalse((repo / "jarvis-cli").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
