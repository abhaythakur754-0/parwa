"""
Tests for app.core.call_lifecycle — Execution Lifecycle Management (Week 10 Day 5)

Covers configuration, lifecycle creation, stage transitions, lifecycle completion,
timeout detection, event listeners, statistics, and data cleanup.
"""

import time
import unittest

from app.core.call_lifecycle import (
    CallLifecycleManager,
    LifecycleConfig,
    LifecycleEvent,
    LifecycleStage,
    LifecycleSnapshot,
    LifecycleStatus,
    StageExecution,
)


def _mgr():
    """Create a fresh CallLifecycleManager for each test."""
    return CallLifecycleManager()


class TestLifecycleConfig(unittest.TestCase):
    """Test configuration management."""

    def test_default_config(self):
        mgr = _mgr()
        cfg = mgr.get_config("co_test")
        self.assertEqual(cfg.company_id, "co_test")
        self.assertEqual(cfg.variant, "parwa")
        self.assertEqual(cfg.timeout_seconds, 300.0)
        self.assertEqual(cfg.max_retries_per_stage, 2)
        self.assertEqual(cfg.retry_delay_ms, 500)
        self.assertEqual(cfg.on_failure_action, "degrade")

    def test_configure_company(self):
        mgr = _mgr()
        cfg = LifecycleConfig(
            company_id="co1",
            variant="mini_parwa",
            timeout_seconds=60.0,
            max_retries_per_stage=1,
            on_failure_action="fail_fast",
        )
        mgr.configure("co1", cfg)
        retrieved = mgr.get_config("co1")
        self.assertEqual(retrieved.variant, "mini_parwa")
        self.assertEqual(retrieved.timeout_seconds, 60.0)
        self.assertEqual(retrieved.max_retries_per_stage, 1)
        self.assertEqual(retrieved.on_failure_action, "fail_fast")

    def test_configure_isolation(self):
        mgr = _mgr()
        mgr.configure("co_a", LifecycleConfig(variant="mini_parwa"))
        mgr.configure("co_b", LifecycleConfig(variant="parwa_high"))
        self.assertEqual(mgr.get_config("co_a").variant, "mini_parwa")
        self.assertEqual(mgr.get_config("co_b").variant, "parwa_high")

    def test_config_all_fields(self):
        mgr = _mgr()
        cfg = LifecycleConfig(
            variant="parwa_high",
            timeout_seconds=120.0,
            max_retries_per_stage=3,
            retry_delay_ms=1000,
            enable_detailed_logging=False,
            stages_to_skip=["context_compression"],
            on_failure_action="retry_all",
        )
        mgr.configure("co1", cfg)
        r = mgr.get_config("co1")
        self.assertFalse(r.enable_detailed_logging)
        self.assertEqual(r.stages_to_skip, ["context_compression"])
        self.assertEqual(r.retry_delay_ms, 1000)


class TestLifecycleStages(unittest.TestCase):
    """Test pipeline stage definitions."""

    def test_mini_parwa_stages(self):
        mgr = _mgr()
        stages = mgr.get_pipeline_stages("mini_parwa")
        self.assertEqual(len(stages), 4)
        self.assertEqual(stages[0], "signal_extraction")
        self.assertIn("intent_classification", stages)
        self.assertIn("response_generation", stages)
        self.assertIn("guardrails_check", stages)

    def test_parwa_stages(self):
        mgr = _mgr()
        stages = mgr.get_pipeline_stages("parwa")
        self.assertEqual(len(stages), 7)
        self.assertIn("rag_retrieval", stages)
        self.assertIn("context_compression", stages)
        self.assertIn("post_processing", stages)

    def test_parwa_high_stages(self):
        mgr = _mgr()
        stages = mgr.get_pipeline_stages("parwa_high")
        self.assertEqual(len(stages), 7)
        self.assertEqual(stages, mgr.get_pipeline_stages("parwa"))

    def test_unknown_variant_defaults(self):
        mgr = _mgr()
        stages = mgr.get_pipeline_stages("unknown_variant")
        self.assertEqual(stages, mgr.get_pipeline_stages("parwa"))

    def test_stage_enums(self):
        self.assertEqual(LifecycleStage.INITIALIZED.value, "initialized")
        self.assertEqual(LifecycleStage.SIGNAL_EXTRACTION.value, "signal_extraction")
        self.assertEqual(LifecycleStage.COMPLETED.value, "completed")
        self.assertEqual(LifecycleStage.FAILED.value, "failed")
        self.assertEqual(LifecycleStage.CANCELLED.value, "cancelled")


class TestLifecycleCreation(unittest.TestCase):
    """Test lifecycle start and initialization."""

    def test_start_returns_id(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        self.assertIsNotNone(lid)
        self.assertIsInstance(lid, str)
        self.assertTrue(len(lid) > 0)

    def test_start_sets_status_running(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        snap = mgr.get_lifecycle("co1", lid)
        self.assertIsNotNone(snap)
        self.assertEqual(snap["status"], "running")

    def test_start_sets_current_stage_initialized(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        snap = mgr.get_lifecycle("co1", lid)
        self.assertEqual(snap["current_stage"], "initialized")

    def test_start_with_metadata(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1", metadata={"key": "value"})
        snap = mgr.get_lifecycle("co1", lid)
        self.assertEqual(snap["metadata"]["key"], "value")

    def test_start_multiple_lifecycles(self):
        mgr = _mgr()
        lid1 = mgr.start_lifecycle("co1", "tkt1")
        lid2 = mgr.start_lifecycle("co1", "tkt2")
        self.assertNotEqual(lid1, lid2)

    def test_start_company_isolation(self):
        mgr = _mgr()
        lid_a = mgr.start_lifecycle("co_a", "tkt1")
        lid_b = mgr.start_lifecycle("co_b", "tkt1")
        self.assertTrue(mgr.is_lifecycle_active("co_a", lid_a))
        self.assertIsNone(mgr.get_lifecycle("co_a", lid_b))
        self.assertIsNone(mgr.get_lifecycle("co_b", lid_a))


class TestStageTransitions(unittest.TestCase):
    """Test stage start/complete/fail/skip."""

    def test_start_stage(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        result = mgr.start_stage("co1", lid, "signal_extraction")
        self.assertTrue(result)
        snap = mgr.get_lifecycle("co1", lid)
        self.assertEqual(snap["current_stage"], "signal_extraction")

    def test_complete_stage(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        result = mgr.complete_stage("co1", lid, "signal_extraction")
        self.assertTrue(result)

    def test_fail_stage(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        result = mgr.fail_stage("co1", lid, "signal_extraction", "timeout error")
        self.assertTrue(result)

    def test_skip_stage(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        result = mgr.skip_stage("co1", lid, "rag_retrieval", "not needed")
        self.assertTrue(result)

    def test_stage_duration_calculated(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        time.sleep(0.01)  # 10ms
        mgr.complete_stage("co1", lid, "signal_extraction")
        dur = mgr.get_stage_duration("co1", lid, "signal_extraction")
        self.assertGreater(dur, 0)

    def test_complete_nonexistent_lifecycle(self):
        mgr = _mgr()
        result = mgr.complete_stage("co1", "fake_id", "signal_extraction")
        self.assertFalse(result)

    def test_multiple_stages_sequential(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        stages = mgr.get_pipeline_stages("parwa")
        for stage in stages[:3]:
            self.assertTrue(mgr.start_stage("co1", lid, stage))
            self.assertTrue(mgr.complete_stage("co1", lid, stage))

    def test_fail_stage_records_error(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        mgr.fail_stage("co1", lid, "signal_extraction", "DB connection lost")
        snap = mgr.get_lifecycle("co1", lid)
        execs = snap["stage_executions"]
        failed = [e for e in execs if e["stage"] == "signal_extraction" and e["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["error"], "DB connection lost")

    def test_stage_metadata_stored(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        mgr.complete_stage("co1", lid, "signal_extraction", metadata={"signals_count": 5})
        snap = mgr.get_lifecycle("co1", lid)
        execs = snap["stage_executions"]
        completed = [e for e in execs if e["stage"] == "signal_extraction"][0]
        self.assertEqual(completed["metadata"]["signals_count"], 5)

    def test_double_complete_stage(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        self.assertTrue(mgr.complete_stage("co1", lid, "signal_extraction"))
        # Second complete re-finds the same stage execution and updates it again
        result = mgr.complete_stage("co1", lid, "signal_extraction")
        self.assertTrue(result)


class TestLifecycleCompletion(unittest.TestCase):
    """Test lifecycle completion and failure."""

    def test_complete_lifecycle(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        result = mgr.complete_lifecycle("co1", lid)
        self.assertTrue(result)
        self.assertFalse(mgr.is_lifecycle_active("co1", lid))

    def test_complete_sets_timestamp(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.complete_lifecycle("co1", lid)
        history = mgr.get_lifecycle_history("co1", "tkt1")
        self.assertEqual(len(history), 1)
        self.assertIsNotNone(history[0].get("completed_at"))

    def test_fail_lifecycle(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        result = mgr.fail_lifecycle("co1", lid, "critical error")
        self.assertTrue(result)
        self.assertFalse(mgr.is_lifecycle_active("co1", lid))

    def test_fail_records_error(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.fail_lifecycle("co1", lid, "out of memory")
        history = mgr.get_lifecycle_history("co1", "tkt1")
        self.assertEqual(len(history), 1)
        self.assertIn("out of memory", history[0].get("metadata", {}).get("failure_error", ""))

    def test_cancel_lifecycle(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        result = mgr.cancel_lifecycle("co1", lid, "user disconnected")
        self.assertTrue(result)
        self.assertFalse(mgr.is_lifecycle_active("co1", lid))

    def test_complete_after_complete(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.complete_lifecycle("co1", lid)
        result = mgr.complete_lifecycle("co1", lid)
        self.assertFalse(result)

    def test_fail_after_complete(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.complete_lifecycle("co1", lid)
        result = mgr.fail_lifecycle("co1", lid, "late error")
        self.assertFalse(result)

    def test_complete_nonexistent(self):
        mgr = _mgr()
        result = mgr.complete_lifecycle("co1", "fake_id")
        self.assertFalse(result)


class TestLifecycleQueries(unittest.TestCase):
    """Test query methods."""

    def test_get_lifecycle_returns_dict(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        snap = mgr.get_lifecycle("co1", lid)
        self.assertIsInstance(snap, dict)
        self.assertIn("lifecycle_id", snap)
        self.assertIn("status", snap)
        self.assertIn("current_stage", snap)
        self.assertIn("stage_executions", snap)
        self.assertIn("started_at", snap)

    def test_get_active_lifecycles(self):
        mgr = _mgr()
        lid1 = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_lifecycle("co1", "tkt2")
        active = mgr.get_active_lifecycles("co1")
        self.assertEqual(len(active), 2)

    def test_completed_not_active(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.complete_lifecycle("co1", lid)
        active = mgr.get_active_lifecycles("co1")
        self.assertEqual(len(active), 0)

    def test_get_lifecycle_history(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.complete_lifecycle("co1", lid)
        history = mgr.get_lifecycle_history("co1", "tkt1")
        self.assertEqual(len(history), 1)

    def test_get_stage_duration(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        dur = mgr.get_stage_duration("co1", lid, "signal_extraction")
        self.assertIsInstance(dur, int)

    def test_get_total_duration(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        time.sleep(0.01)
        dur = mgr.get_total_duration("co1", lid)
        self.assertGreaterEqual(dur, 0)

    def test_is_lifecycle_active_true(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        self.assertTrue(mgr.is_lifecycle_active("co1", lid))

    def test_is_lifecycle_active_false(self):
        mgr = _mgr()
        self.assertFalse(mgr.is_lifecycle_active("co1", "nonexistent"))


class TestLifecycleTimeout(unittest.TestCase):
    """Test timeout detection."""

    def test_get_timeout_status_not_timed_out(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        info = mgr.get_timeout_status("co1", lid)
        self.assertFalse(info["timed_out"])

    def test_get_timeout_status_timed_out(self):
        mgr = _mgr()
        mgr.configure("co1", LifecycleConfig(timeout_seconds=0.001))
        lid = mgr.start_lifecycle("co1", "tkt1")
        time.sleep(0.01)
        info = mgr.get_timeout_status("co1", lid)
        self.assertTrue(info["timed_out"])

    def test_timeout_with_custom_config(self):
        mgr = _mgr()
        mgr.configure("co_timeout", LifecycleConfig(timeout_seconds=0.001))
        lid = mgr.start_lifecycle("co_timeout", "tkt1")
        time.sleep(0.01)
        info = mgr.get_timeout_status("co_timeout", lid)
        self.assertTrue(info["timed_out"])

    def test_timeout_nonexistent_lifecycle(self):
        mgr = _mgr()
        info = mgr.get_timeout_status("co1", "nonexistent")
        self.assertIn("timed_out", info)


class TestLifecycleEvents(unittest.TestCase):
    """Test event listeners."""

    def test_add_listener(self):
        mgr = _mgr()
        events = []
        mgr.add_event_listener(lambda etype, lid, data: events.append((etype, lid)))
        mgr.start_lifecycle("co1", "tkt1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "lifecycle_started")

    def test_remove_listener(self):
        mgr = _mgr()
        events = []
        cb = lambda eid, etype, data: events.append(etype)
        mgr.add_event_listener(cb)
        mgr.start_lifecycle("co1", "tkt1")
        self.assertEqual(len(events), 1)
        mgr.remove_event_listener(cb)
        mgr.start_lifecycle("co1", "tkt2")
        self.assertEqual(len(events), 1)  # no new event

    def test_start_lifecycle_emits_event(self):
        mgr = _mgr()
        events = []
        mgr.add_event_listener(lambda etype, lid, data: events.append(etype))
        mgr.start_lifecycle("co1", "tkt1")
        self.assertEqual(events[0], "lifecycle_started")

    def test_stage_complete_emits_event(self):
        mgr = _mgr()
        events = []
        mgr.add_event_listener(lambda etype, lid, data: events.append(etype))
        lid = mgr.start_lifecycle("co1", "tkt1")
        mgr.start_stage("co1", lid, "signal_extraction")
        mgr.complete_stage("co1", lid, "signal_extraction")
        self.assertIn("stage_completed", events)

    def test_listener_error_doesnt_crash(self):
        mgr = _mgr()
        def bad_listener(eid, etype, data):
            raise RuntimeError("listener error")
        mgr.add_event_listener(bad_listener)
        lid = mgr.start_lifecycle("co1", "tkt1")
        self.assertIsNotNone(lid)


class TestLifecycleSummary(unittest.TestCase):
    """Test summary and statistics."""

    def test_get_lifecycle_summary_keys(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        summary = mgr.get_lifecycle_summary("co1", lid)
        self.assertIsInstance(summary, dict)
        self.assertIn("lifecycle_id", summary)
        self.assertIn("status", summary)

    def test_get_statistics_empty(self):
        mgr = _mgr()
        stats = mgr.get_statistics("co1")
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats["total_lifecycles"], 0)

    def test_get_statistics_with_data(self):
        mgr = _mgr()
        mgr.start_lifecycle("co1", "tkt1")
        mgr.start_lifecycle("co1", "tkt2")
        mgr.start_lifecycle("co1", "tkt3")
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["total_lifecycles"], 3)

    def test_summary_includes_variant(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1", variant="mini_parwa")
        summary = mgr.get_lifecycle_summary("co1", lid)
        self.assertEqual(summary["variant"], "mini_parwa")

    def test_summary_includes_durations(self):
        mgr = _mgr()
        lid = mgr.start_lifecycle("co1", "tkt1")
        summary = mgr.get_lifecycle_summary("co1", lid)
        self.assertIn("total_duration_ms", summary)

    def test_statistics_failure_rate(self):
        mgr = _mgr()
        lid1 = mgr.start_lifecycle("co1", "tkt1")
        mgr.complete_lifecycle("co1", lid1)
        lid2 = mgr.start_lifecycle("co1", "tkt2")
        mgr.fail_lifecycle("co1", lid2, "error")
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["failed"], 1)


class TestLifecycleCleanup(unittest.TestCase):
    """Test data cleanup."""

    def test_clear_company_data(self):
        mgr = _mgr()
        mgr.start_lifecycle("co1", "tkt1")
        mgr.clear_company_data("co1")
        self.assertEqual(len(mgr.get_active_lifecycles("co1")), 0)
        self.assertEqual(len(mgr.get_lifecycle_history("co1")), 0)

    def test_clear_company_isolation(self):
        mgr = _mgr()
        mgr.start_lifecycle("co_a", "tkt1")
        mgr.start_lifecycle("co_b", "tkt1")
        mgr.clear_company_data("co_a")
        self.assertEqual(len(mgr.get_active_lifecycles("co_a")), 0)
        self.assertEqual(len(mgr.get_active_lifecycles("co_b")), 1)

    def test_clear_nonexistent_company(self):
        mgr = _mgr()
        mgr.clear_company_data("nonexistent")
        # Should not crash

    def test_clear_resets_statistics(self):
        mgr = _mgr()
        mgr.start_lifecycle("co1", "tkt1")
        mgr.start_lifecycle("co1", "tkt2")
        mgr.clear_company_data("co1")
        stats = mgr.get_statistics("co1")
        self.assertEqual(stats["total_lifecycles"], 0)


class TestEnumValues(unittest.TestCase):
    """Test enum completeness."""

    def test_lifecycle_stage_values(self):
        stages = [s.value for s in LifecycleStage]
        for expected in ["initialized", "signal_extraction", "response_generation",
                        "guardrails_check", "completed", "failed", "cancelled"]:
            self.assertIn(expected, stages)

    def test_lifecycle_event_values(self):
        events = [e.value for e in LifecycleEvent]
        for expected in ["stage_started", "stage_completed", "stage_failed",
                        "stage_skipped", "stage_retry", "lifecycle_started",
                        "lifecycle_completed", "lifecycle_failed",
                        "lifecycle_cancelled", "timeout"]:
            self.assertIn(expected, events)

    def test_lifecycle_status_values(self):
        statuses = [s.value for s in LifecycleStatus]
        for expected in ["pending", "running", "completed", "failed",
                        "cancelled", "timed_out"]:
            self.assertIn(expected, statuses)


if __name__ == "__main__":
    unittest.main()
