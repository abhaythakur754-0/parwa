"""
Comprehensive tests for app.core.session_continuity module.

Covers: configuration, lock acquisition/release/expiry, collision strategies,
session CRUD, stale detection, handoff, query methods, event listeners,
statistics, data cleanup, and enum completeness.
"""

import time
import unittest

from app.core.session_continuity import (
    CollisionAction,
    ContinuityConfig,
    LockStatus,
    SessionContinuityManager,
    SessionStatus,
)


def _mgr():
    """Create a fresh SessionContinuityManager for each test."""
    return SessionContinuityManager()


class TestContinuityConfig(unittest.TestCase):
    """Test config management (4 tests)."""

    def test_default_config(self):
        """Defaults: lock_timeout=300, heartbeat_interval=30, collision_strategy='wait'."""
        mgr = _mgr()
        config = mgr.get_config("co-defaults")
        self.assertEqual(config.lock_timeout_seconds, 300.0)
        self.assertEqual(config.heartbeat_interval_seconds, 30.0)
        self.assertEqual(config.collision_strategy, "wait")
        self.assertEqual(config.max_heartbeat_misses, 3)
        self.assertEqual(config.session_ttl_seconds, 3600.0)
        self.assertTrue(config.enable_heartbeat_monitoring)
        self.assertEqual(config.max_concurrent_sessions_per_agent, 10)
        self.assertEqual(config.handoff_timeout_seconds, 60.0)
        self.assertEqual(config.company_id, "co-defaults")

    def test_configure_company(self):
        """Custom config stored and retrieved."""
        mgr = _mgr()
        cfg = ContinuityConfig(
            lock_timeout_seconds=60.0,
            heartbeat_interval_seconds=5.0,
            max_heartbeat_misses=2,
            collision_strategy="reject",
        )
        result = mgr.configure("co-custom", cfg)
        self.assertTrue(result["success"])
        retrieved = mgr.get_config("co-custom")
        self.assertEqual(retrieved.lock_timeout_seconds, 60.0)
        self.assertEqual(retrieved.heartbeat_interval_seconds, 5.0)
        self.assertEqual(retrieved.collision_strategy, "reject")
        self.assertEqual(retrieved.company_id, "co-custom")

    def test_config_isolation(self):
        """Company A config doesn't affect B."""
        mgr = _mgr()
        cfg_a = ContinuityConfig(lock_timeout_seconds=10.0, collision_strategy="reject")
        cfg_b = ContinuityConfig(lock_timeout_seconds=999.0, collision_strategy="queue")
        mgr.configure("co-a", cfg_a)
        mgr.configure("co-b", cfg_b)
        self.assertEqual(mgr.get_config("co-a").lock_timeout_seconds, 10.0)
        self.assertEqual(mgr.get_config("co-b").lock_timeout_seconds, 999.0)
        self.assertEqual(mgr.get_config("co-a").collision_strategy, "reject")
        self.assertEqual(mgr.get_config("co-b").collision_strategy, "queue")

    def test_config_all_fields(self):
        """All ContinuityConfig fields accessible."""
        mgr = _mgr()
        cfg = ContinuityConfig(
            company_id="co-fields",
            lock_timeout_seconds=120.0,
            heartbeat_interval_seconds=10.0,
            max_heartbeat_misses=5,
            collision_strategy="merge",
            session_ttl_seconds=7200.0,
            enable_heartbeat_monitoring=False,
            max_concurrent_sessions_per_agent=3,
            handoff_timeout_seconds=30.0,
        )
        mgr.configure("co-fields", cfg)
        r = mgr.get_config("co-fields")
        self.assertEqual(r.company_id, "co-fields")
        self.assertEqual(r.lock_timeout_seconds, 120.0)
        self.assertEqual(r.heartbeat_interval_seconds, 10.0)
        self.assertEqual(r.max_heartbeat_misses, 5)
        self.assertEqual(r.collision_strategy, "merge")
        self.assertEqual(r.session_ttl_seconds, 7200.0)
        self.assertFalse(r.enable_heartbeat_monitoring)
        self.assertEqual(r.max_concurrent_sessions_per_agent, 3)
        self.assertEqual(r.handoff_timeout_seconds, 30.0)


class TestLockAcquisition(unittest.TestCase):
    """Test lock acquire/release (8 tests)."""

    def test_acquire_lock_success(self):
        """First acquire returns (True, 'acquired', 'acquired')."""
        mgr = _mgr()
        result = mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertTrue(result["success"])
        self.assertEqual(result["lock_status"], "acquired")
        self.assertEqual(result["action"], "acquired")

    def test_acquire_lock_idempotent(self):
        """Same agent re-acquires returns True with action='renewed'."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "renewed")

    def test_acquire_lock_contested(self):
        """Different agent gets (False, 'contested', 'wait') with default strategy."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.acquire_lock("co1", "tkt1", "agent-B")
        self.assertFalse(result["success"])
        self.assertEqual(result["lock_status"], "contested")
        self.assertEqual(result["action"], "wait")

    def test_release_lock_success(self):
        """Owner can release."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.release_lock("co1", "tkt1", "agent-A")
        self.assertTrue(result["success"])
        self.assertEqual(result["lock_status"], "released")

    def test_release_lock_non_owner(self):
        """Non-owner cannot release."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.release_lock("co1", "tkt1", "agent-B")
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_release_lock_not_found(self):
        """Returns False gracefully when no lock exists."""
        mgr = _mgr()
        result = mgr.release_lock("co1", "tkt-nonexist", "agent-A")
        self.assertFalse(result["success"])
        self.assertEqual(result["lock_status"], "not_found")

    def test_renew_lock_success(self):
        """Extends TTL."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        old_info = mgr.get_lock_info("co1", "tkt1")
        old_expires = old_info["expires_at"]
        time.sleep(0.01)
        result = mgr.renew_lock("co1", "tkt1", "agent-A")
        self.assertTrue(result["success"])
        self.assertIn("new_expires_at", result)
        new_info = mgr.get_lock_info("co1", "tkt1")
        self.assertNotEqual(new_info["expires_at"], old_expires)

    def test_renew_lock_non_owner(self):
        """Cannot renew a lock owned by another agent."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.renew_lock("co1", "tkt1", "agent-B")
        self.assertFalse(result["success"])
        self.assertIn("error", result)


class TestLockExpiry(unittest.TestCase):
    """Test lock expiration (4 tests)."""

    def test_expired_lock_reacquired(self):
        """Configure very short timeout, wait, re-acquire by different agent."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(lock_timeout_seconds=0.01))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        time.sleep(0.05)
        result = mgr.acquire_lock("co1", "tkt1", "agent-B")
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "acquired")

    def test_expired_lock_auto_detected(self):
        """check_lock returns 'expired' for stale lock."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(lock_timeout_seconds=0.01))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        time.sleep(0.05)
        status = mgr.check_lock("co1", "tkt1")
        self.assertFalse(status["locked"])
        self.assertEqual(status["status"], "expired")

    def test_renew_extends_expiry(self):
        """New expires_at > old expires_at."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(lock_timeout_seconds=1.0))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        info_before = mgr.get_lock_info("co1", "tkt1")
        expires_before = info_before["expires_at"]
        time.sleep(0.05)
        mgr.renew_lock("co1", "tkt1", "agent-A")
        info_after = mgr.get_lock_info("co1", "tkt1")
        expires_after = info_after["expires_at"]
        self.assertGreater(expires_after, expires_before)

    def test_lock_expiry_collision_strategy(self):
        """After expiry, new agent can acquire regardless of collision strategy."""
        mgr = _mgr()
        mgr.configure(
            "co1",
            ContinuityConfig(
                lock_timeout_seconds=0.01,
                collision_strategy="reject",
            ),
        )
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        time.sleep(0.05)
        result = mgr.acquire_lock("co1", "tkt1", "agent-B")
        self.assertTrue(result["success"])
        self.assertEqual(result["lock_status"], "acquired")


class TestCollisionStrategies(unittest.TestCase):
    """Test different collision resolution (6 tests)."""

    def test_wait_strategy(self):
        """Default wait returns contested."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(collision_strategy="wait"))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.acquire_lock("co1", "tkt1", "agent-B")
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "wait")

    def test_reject_strategy(self):
        """Returns rejected."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(collision_strategy="reject"))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.acquire_lock("co1", "tkt1", "agent-B")
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "reject")

    def test_queue_strategy(self):
        """Returns queued."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(collision_strategy="queue"))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.acquire_lock("co1", "tkt1", "agent-B")
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "queue")

    def test_merge_strategy(self):
        """Returns merged (success=True in merge mode)."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(collision_strategy="merge"))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.acquire_lock("co1", "tkt1", "agent-B")
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "merge")

    def test_preempt_priority(self):
        """Higher priority agent preempts."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(collision_strategy="preempt"))
        mgr.acquire_lock("co1", "tkt1", "agent-A", metadata={"priority": 1})
        result = mgr.acquire_lock("co1", "tkt1", "agent-B", metadata={"priority": 10})
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "acquired")
        self.assertEqual(mgr.get_ticket_owner("co1", "tkt1"), "agent-B")

    def test_same_owner_no_collision(self):
        """Re-acquire always succeeds (no collision)."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(collision_strategy="reject"))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertTrue(result["success"])


class TestSessionManagement(unittest.TestCase):
    """Test session CRUD (8 tests)."""

    def test_register_session(self):
        """Creates session, returns session_id."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        self.assertTrue(result["success"])
        self.assertIn("session_id", result)

    def test_register_requires_lock(self):
        """Fails if no lock held."""
        mgr = _mgr()
        result = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_update_session(self):
        """Updates stage_reached, processing_steps."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        sid = reg["session_id"]
        result = mgr.update_session(
            "co1",
            sid,
            {
                "stage_reached": "classification",
                "processing_steps": 5,
            },
        )
        self.assertTrue(result["success"])
        session = mgr.get_session("co1", sid)
        self.assertEqual(session["stage_reached"], "classification")
        self.assertEqual(session["processing_steps"], 5)

    def test_heartbeat(self):
        """Updates last_heartbeat_at."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        sid = reg["session_id"]
        session_before = mgr.get_session("co1", sid)
        hb_before = session_before["last_heartbeat_at"]
        time.sleep(0.01)
        result = mgr.heartbeat("co1", sid)
        self.assertTrue(result["success"])
        session_after = mgr.get_session("co1", sid)
        self.assertNotEqual(session_after["last_heartbeat_at"], hb_before)

    def test_complete_session(self):
        """Status=completed, lock released."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        sid = reg["session_id"]
        result = mgr.complete_session("co1", sid)
        self.assertTrue(result["success"])
        session = mgr.get_session("co1", sid)
        self.assertEqual(session["status"], "completed")
        self.assertIsNotNone(session["completed_at"])
        self.assertFalse(mgr.is_ticket_locked("co1", "tkt1"))

    def test_fail_session(self):
        """Status=failed, lock released."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        sid = reg["session_id"]
        result = mgr.fail_session("co1", sid, "Something went wrong")
        self.assertTrue(result["success"])
        session = mgr.get_session("co1", sid)
        self.assertEqual(session["status"], "failed")
        self.assertEqual(session["metadata"]["error"], "Something went wrong")
        self.assertFalse(mgr.is_ticket_locked("co1", "tkt1"))

    def test_session_metadata(self):
        """Metadata preserved."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session(
            "co1",
            "tkt1",
            "agent-A",
            "standard",
            metadata={"customer_tier": "premium", "channel": "email"},
        )
        sid = reg["session_id"]
        session = mgr.get_session("co1", sid)
        self.assertEqual(session["metadata"]["customer_tier"], "premium")
        self.assertEqual(session["metadata"]["channel"], "email")

    def test_multiple_sessions_same_ticket(self):
        """Tracked together under same ticket."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg1 = mgr.register_session("co1", "tkt1", "agent-A", "variant-x")
        reg2 = mgr.register_session("co1", "tkt1", "agent-A", "variant-y")
        active = mgr.get_active_sessions("co1")
        ticket_ids = [s["ticket_id"] for s in active]
        self.assertEqual(ticket_ids.count("tkt1"), 2)
        variants = sorted([s["variant"] for s in active])
        self.assertEqual(variants, ["variant-x", "variant-y"])


class TestStaleDetection(unittest.TestCase):
    """Test heartbeat/stale detection (5 tests)."""

    def test_no_stale_when_healthy(self):
        """Fresh session not stale."""
        mgr = _mgr()
        mgr.configure(
            "co1",
            ContinuityConfig(
                heartbeat_interval_seconds=1.0,
                max_heartbeat_misses=1,
            ),
        )
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        mgr.heartbeat("co1", reg["session_id"])
        result = mgr.detect_stale_sessions("co1")
        self.assertEqual(len(result["stale_sessions"]), 0)
        self.assertTrue(result["monitoring_enabled"])

    def test_detect_stale_sessions(self):
        """Configure short heartbeat, wait, detect."""
        mgr = _mgr()
        mgr.configure(
            "co1",
            ContinuityConfig(
                heartbeat_interval_seconds=0.01,
                max_heartbeat_misses=1,
            ),
        )
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        time.sleep(0.05)
        result = mgr.detect_stale_sessions("co1")
        self.assertTrue(result["monitoring_enabled"])
        stale_ids = [s["session_id"] for s in result["stale_sessions"]]
        self.assertIn(reg["session_id"], stale_ids)

    def test_force_release_stale(self):
        """Releases expired lock."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(lock_timeout_seconds=0.01))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        time.sleep(0.05)
        result = mgr.force_release_stale("co1", "tkt1")
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["sessions_expired"], 1)
        self.assertFalse(mgr.is_ticket_locked("co1", "tkt1"))

    def test_force_release_nonexistent(self):
        """Returns gracefully when no lock found."""
        mgr = _mgr()
        result = mgr.force_release_stale("co1", "tkt-nonexist")
        self.assertFalse(result["success"])
        self.assertEqual(result["sessions_expired"], 0)

    def test_stale_after_max_misses(self):
        """Multiple missed heartbeats counted correctly."""
        mgr = _mgr()
        mgr.configure(
            "co1",
            ContinuityConfig(
                heartbeat_interval_seconds=0.01,
                max_heartbeat_misses=3,
            ),
        )
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        time.sleep(0.02)
        self.assertEqual(len(mgr.detect_stale_sessions("co1")["stale_sessions"]), 0)
        time.sleep(0.02)
        stale = mgr.detect_stale_sessions("co1")["stale_sessions"]
        self.assertTrue(len(stale) > 0)
        self.assertEqual(stale[0]["threshold_seconds"], 0.03)


class TestHandoff(unittest.TestCase):
    """Test session handoff (6 tests)."""

    def test_initiate_handoff_success(self):
        """Ownership transferred."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        result = mgr.initiate_handoff("co1", "tkt1", "agent-A", "agent-B", "escalation")
        self.assertTrue(result["success"])
        self.assertEqual(mgr.get_ticket_owner("co1", "tkt1"), "agent-B")

    def test_handoff_records_created(self):
        """Record in handoff_history."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        mgr.initiate_handoff("co1", "tkt1", "agent-A", "agent-B", "reason-x")
        history = mgr.get_handoff_history("co1", "tkt1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["from_agent"], "agent-A")
        self.assertEqual(history[0]["to_agent"], "agent-B")
        self.assertEqual(history[0]["reason"], "reason-x")
        self.assertTrue(history[0]["success"])

    def test_handoff_from_non_owner(self):
        """Fails gracefully."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        result = mgr.initiate_handoff("co1", "tkt1", "agent-C", "agent-B", "escalation")
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_handoff_context_transferred(self):
        """Context dict preserved."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        ctx = {"summary": "Customer upset", "notes": "Follow up required"}
        mgr.initiate_handoff(
            "co1", "tkt1", "agent-A", "agent-B", "escalation", context=ctx
        )
        history = mgr.get_handoff_history("co1", "tkt1")
        self.assertEqual(history[0]["context_transferred"], ctx)

    def test_handoff_new_session_created(self):
        """New agent can create a session on the ticket after handoff."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        mgr.initiate_handoff("co1", "tkt1", "agent-A", "agent-B", "escalation")
        reg = mgr.register_session("co1", "tkt1", "agent-B", "escalation-variant")
        self.assertTrue(reg["success"])

    def test_handoff_history_retrieved(self):
        """get_handoff_history works and returns newest first."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        mgr.initiate_handoff("co1", "tkt1", "agent-A", "agent-B", "reason-1")
        mgr.initiate_handoff("co1", "tkt1", "agent-B", "agent-C", "reason-2")
        history = mgr.get_handoff_history("co1", "tkt1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["to_agent"], "agent-C")
        self.assertEqual(history[1]["to_agent"], "agent-B")


class TestQueryMethods(unittest.TestCase):
    """Test various query methods (7 tests)."""

    def test_get_session(self):
        """Returns session dict."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        session = mgr.get_session("co1", reg["session_id"])
        self.assertIsNotNone(session)
        self.assertEqual(session["session_id"], reg["session_id"])
        self.assertEqual(session["ticket_id"], "tkt1")
        self.assertEqual(session["agent_id"], "agent-A")
        self.assertEqual(session["variant"], "standard")
        self.assertEqual(session["status"], "active")

    def test_get_active_sessions(self):
        """Only active ones returned."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg1 = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        active = mgr.get_active_sessions("co1")
        self.assertEqual(len(active), 1)
        mgr.complete_session("co1", reg1["session_id"])
        active = mgr.get_active_sessions("co1")
        self.assertEqual(len(active), 0)

    def test_get_agent_sessions(self):
        """Filtered by agent."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        mgr.acquire_lock("co1", "tkt2", "agent-B")
        mgr.register_session("co1", "tkt2", "agent-B", "premium")
        sessions_a = mgr.get_agent_sessions("co1", "agent-A")
        sessions_b = mgr.get_agent_sessions("co1", "agent-B")
        self.assertEqual(len(sessions_a), 1)
        self.assertEqual(len(sessions_b), 1)
        self.assertEqual(sessions_a[0]["agent_id"], "agent-A")
        self.assertEqual(sessions_b[0]["agent_id"], "agent-B")

    def test_get_collision_events(self):
        """Returns collision history."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.acquire_lock("co1", "tkt1", "agent-B")
        events = mgr.get_collision_events("co1", "tkt1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["existing_owner"], "agent-A")
        self.assertEqual(events[0]["contender_id"], "agent-B")

    def test_is_ticket_locked_true(self):
        """Locked ticket returns True."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertTrue(mgr.is_ticket_locked("co1", "tkt1"))

    def test_is_ticket_locked_false(self):
        """Unlocked returns False."""
        mgr = _mgr()
        self.assertFalse(mgr.is_ticket_locked("co1", "tkt1"))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.release_lock("co1", "tkt1", "agent-A")
        self.assertFalse(mgr.is_ticket_locked("co1", "tkt1"))

    def test_get_ticket_owner(self):
        """Returns owner agent_id."""
        mgr = _mgr()
        self.assertIsNone(mgr.get_ticket_owner("co1", "tkt1"))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertEqual(mgr.get_ticket_owner("co1", "tkt1"), "agent-A")


class TestContinuityEvents(unittest.TestCase):
    """Test event listeners (4 tests)."""

    def test_add_listener_receives_events(self):
        """Callback invoked on events."""
        mgr = _mgr()
        received = []
        mgr.add_event_listener(lambda et, pl: received.append((et, pl)))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertTrue(len(received) > 0)
        event_types = [r[0] for r in received]
        self.assertIn("lock_acquired", event_types)

    def test_remove_listener(self):
        """Stops receiving after removal."""
        mgr = _mgr()
        received = []

        def cb(et, pl):
            return received.append((et, pl))

        mgr.add_event_listener(cb)
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        count_after_add = len(received)
        mgr.remove_event_listener(cb)
        mgr.acquire_lock("co1", "tkt2", "agent-B")
        self.assertEqual(len(received), count_after_add)

    def test_listener_error_safe(self):
        """Bad listener doesn't crash the system."""
        mgr = _mgr()

        def bad_listener(et, pl):
            raise RuntimeError("listener crash")

        mgr.add_event_listener(bad_listener)
        result = mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertTrue(result["success"])

    def test_multiple_listeners(self):
        """All listeners get events."""
        mgr = _mgr()
        received_a = []
        received_b = []
        mgr.add_event_listener(lambda et, pl: received_a.append(et))
        mgr.add_event_listener(lambda et, pl: received_b.append(et))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        self.assertEqual(len(received_a), 1)
        self.assertEqual(len(received_b), 1)
        self.assertEqual(received_a[0], "lock_acquired")
        self.assertEqual(received_b[0], "lock_acquired")


class TestContinuityStatistics(unittest.TestCase):
    """Test statistics (4 tests)."""

    def test_empty_stats(self):
        """Returns zeros for a fresh manager."""
        mgr = _mgr()
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["company_id"], "co1")
        self.assertEqual(stats["total_locks_acquired"], 0)
        self.assertEqual(stats["total_locks_released"], 0)
        self.assertEqual(stats["active_locks"], 0)
        self.assertEqual(stats["active_sessions"], 0)
        self.assertEqual(stats["completed_sessions"], 0)
        self.assertEqual(stats["failed_sessions"], 0)
        self.assertEqual(stats["company_collisions"], 0)
        self.assertEqual(stats["stale_sessions_recovered"], 0)
        self.assertEqual(stats["handoff_count"], 0)

    def test_stats_with_locks(self):
        """Reflects lock activity."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.acquire_lock("co1", "tkt2", "agent-B")
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["total_locks_acquired"], 2)
        self.assertEqual(stats["active_locks"], 2)
        self.assertEqual(stats["total_acquire_attempts"], 2)
        mgr.release_lock("co1", "tkt1", "agent-A")
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["total_locks_released"], 1)

    def test_stats_with_collisions(self):
        """Collision count tracked."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.acquire_lock("co1", "tkt1", "agent-B")
        stats = mgr.get_statistics("co1")
        self.assertGreater(stats["company_collisions"], 0)
        self.assertGreater(stats["total_collisions"], 0)

    def test_stats_with_sessions(self):
        """Session counts tracked."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        reg = mgr.register_session("co1", "tkt1", "agent-A", "standard")
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["active_sessions"], 1)
        self.assertIn("agent-A", stats["agent_counts"])
        mgr.complete_session("co1", reg["session_id"])
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["active_sessions"], 0)
        self.assertEqual(stats["completed_sessions"], 1)


class TestContinuityCleanup(unittest.TestCase):
    """Test data cleanup (3 tests)."""

    def test_clear_company_data(self):
        """All data removed."""
        mgr = _mgr()
        mgr.configure("co1", ContinuityConfig(lock_timeout_seconds=60.0))
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.acquire_lock("co1", "tkt2", "agent-B")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        mgr.acquire_lock("co1", "tkt1", "agent-B")
        mgr.initiate_handoff("co1", "tkt1", "agent-A", "agent-B", "reason-x")
        result = mgr.clear_company_data("co1")
        self.assertTrue(result["success"])
        counts = result["cleared_counts"]
        self.assertGreaterEqual(counts["locks"], 1)
        self.assertGreaterEqual(counts["sessions"], 1)
        self.assertGreaterEqual(counts["handoff_records"], 1)
        self.assertEqual(mgr.get_active_sessions("co1"), [])
        self.assertFalse(mgr.is_ticket_locked("co1", "tkt1"))

    def test_clear_isolation(self):
        """Other companies unaffected."""
        mgr = _mgr()
        mgr.acquire_lock("co1", "tkt1", "agent-A")
        mgr.register_session("co1", "tkt1", "agent-A", "standard")
        mgr.acquire_lock("co2", "tkt-x", "agent-B")
        mgr.register_session("co2", "tkt-x", "agent-B", "premium")
        mgr.clear_company_data("co1")
        self.assertTrue(mgr.is_ticket_locked("co2", "tkt-x"))
        active_co2 = mgr.get_active_sessions("co2")
        self.assertEqual(len(active_co2), 1)

    def test_clear_nonexistent(self):
        """Handled gracefully for unknown company."""
        mgr = _mgr()
        result = mgr.clear_company_data("co-nonexist")
        self.assertTrue(result["success"])
        counts = result["cleared_counts"]
        self.assertEqual(counts["locks"], 0)
        self.assertEqual(counts["sessions"], 0)
        self.assertEqual(counts["collision_events"], 0)
        self.assertEqual(counts["handoff_records"], 0)


class TestEnumValues(unittest.TestCase):
    """Test enum completeness (3 tests)."""

    def test_session_status_values(self):
        """Key SessionStatus values exist."""
        expected = {"active", "completed", "failed", "handoff", "preempted", "expired"}
        actual = {s.value for s in SessionStatus}
        self.assertEqual(actual, expected)

    def test_collision_action_values(self):
        """Key CollisionAction values exist."""
        expected = {"wait", "preempt", "merge", "reject", "queue"}
        actual = {a.value for a in CollisionAction}
        self.assertEqual(actual, expected)

    def test_lock_status_values(self):
        """Key LockStatus values exist."""
        expected = {"acquired", "contested", "released", "expired", "not_found"}
        actual = {item.value for item in LockStatus}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
