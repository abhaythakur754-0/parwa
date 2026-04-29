"""
Comprehensive unit tests for state_migration module.

Tests: 55+
Categories:
  - Single migration steps (v1->v2, v2->v3, v3->v4, v4->v5, v5->v6) (10)
  - Multi-step migration (v1->v6) (4)
  - Dry-run mode (4)
  - Backward compatibility / old format loading (5)
  - Migration validation (5)
  - Batch migration (5)
  - Migration path calculation (4)
  - Rollback capability (8)
  - Unknown version handling (4)
  - Already-at-target version (3)
  - Missing field defaults (3)
  - Edge cases (3)
"""

import copy

import pytest
from app.core.state_migration import (
    BatchMigrationResult,
    MigrationResult,
    StateMigrator,
    ValidationResult,
    _migrate_v1_to_v2,
    _migrate_v2_to_v3,
    _migrate_v3_to_v4,
    _migrate_v4_to_v5,
    _migrate_v5_to_v6,
)

# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def migrator() -> StateMigrator:
    """Fresh migrator instance for each test."""
    return StateMigrator(latest_version=6)


def _v1_state(**overrides) -> dict:
    """Create a v1 state dict with base fields."""
    state = {
        "query": "Hello, how can I help?",
        "gsd_state": "new",
    }
    state.update(overrides)
    return state


def _v2_state(**overrides) -> dict:
    """Create a v2 state dict."""
    state = _v1_state()
    state["reasoning_thread"] = []
    state["_version"] = 2
    state.update(overrides)
    return state


def _v3_state(**overrides) -> dict:
    """Create a v3 state dict."""
    state = _v2_state()
    state["reflexion_trace"] = None
    state["_version"] = 3
    state.update(overrides)
    return state


def _v4_state(**overrides) -> dict:
    """Create a v4 state dict."""
    state = _v3_state()
    state["technique_token_budget"] = 1500
    state["_version"] = 4
    state.update(overrides)
    return state


def _v5_state(**overrides) -> dict:
    """Create a v5 state dict."""
    state = _v4_state()
    state["_version"] = 5
    state.update(overrides)
    return state


def _v6_state(**overrides) -> dict:
    """Create a v6 state dict."""
    state = _v5_state()
    state["signals"] = {
        "intent_confidence": 0.0,
        "urgency_level": "medium",
        "sentiment_score": 0.0,
        "language_code": "en",
    }
    state["_version"] = 6
    state.update(overrides)
    return state


# ── Single Migration Steps ──────────────────────────────────────


class TestSingleMigrationSteps:
    """Tests for individual migration step functions."""

    def test_v1_to_v2_adds_reasoning_thread(self):
        state = _v1_state()
        new_state, changes, warnings = _migrate_v1_to_v2(
            copy.deepcopy(state),
        )
        assert "reasoning_thread" in new_state
        assert new_state["reasoning_thread"] == []
        assert new_state["_version"] == 2
        assert any("reasoning_thread" in c for c in changes)

    def test_v1_to_v2_preserves_existing_fields(self):
        state = _v1_state()
        new_state, _, _ = _migrate_v1_to_v2(
            copy.deepcopy(state),
        )
        assert new_state["query"] == "Hello, how can I help?"
        assert new_state["gsd_state"] == "new"

    def test_v2_to_v3_adds_reflexion_trace(self):
        state = _v2_state()
        new_state, changes, _ = _migrate_v2_to_v3(
            copy.deepcopy(state),
        )
        assert new_state["reflexion_trace"] is None
        assert new_state["_version"] == 3
        assert any("reflexion_trace" in c for c in changes)

    def test_v3_to_v4_adds_token_budget(self):
        state = _v3_state()
        new_state, changes, _ = _migrate_v3_to_v4(
            copy.deepcopy(state),
        )
        assert new_state["technique_token_budget"] == 1500
        assert new_state["_version"] == 4
        assert any("technique_token_budget" in c for c in changes)

    def test_v4_to_v5_converts_int_gsd_state(self):
        state = _v4_state(gsd_state=2)
        new_state, changes, _ = _migrate_v4_to_v5(
            copy.deepcopy(state),
        )
        assert new_state["gsd_state"] == "processing"
        assert new_state["_version"] == 5
        assert any("gsd_state" in c for c in changes)

    def test_v4_to_v5_unknown_int_fallback(self):
        state = _v4_state(gsd_state=99)
        new_state, changes, warnings = _migrate_v4_to_v5(
            copy.deepcopy(state),
        )
        assert new_state["gsd_state"] == "new"
        assert any("fallback" in c for c in changes)

    def test_v4_to_v5_string_gsd_state_unchanged(self):
        state = _v4_state(gsd_state="processing")
        new_state, _, warnings = _migrate_v4_to_v5(
            copy.deepcopy(state),
        )
        assert new_state["gsd_state"] == "processing"
        assert any("already a string" in w for w in warnings)

    def test_v5_to_v6_adds_signals(self):
        state = _v5_state()
        new_state, changes, _ = _migrate_v5_to_v6(
            copy.deepcopy(state),
        )
        assert "signals" in new_state
        assert isinstance(new_state["signals"], dict)
        assert new_state["signals"]["urgency_level"] == "medium"
        assert new_state["_version"] == 6

    def test_v5_to_v6_merges_partial_signals(self):
        state = _v5_state()
        state["signals"] = {"intent_confidence": 0.8}
        new_state, changes, warnings = _migrate_v5_to_v6(
            copy.deepcopy(state),
        )
        assert new_state["signals"]["intent_confidence"] == 0.8
        assert "urgency_level" in new_state["signals"]
        assert any("Merged" in c for c in changes)

    def test_v5_to_v6_replaces_invalid_signals(self):
        state = _v5_state()
        state["signals"] = "not_a_dict"
        new_state, changes, warnings = _migrate_v5_to_v6(
            copy.deepcopy(state),
        )
        assert isinstance(new_state["signals"], dict)
        assert any("defaults" in c for c in changes)

    def test_migration_does_not_overwrite_existing_field(self):
        """If field already exists, it's preserved."""
        state = _v1_state(reasoning_thread=["existing"])
        new_state, _, warnings = _migrate_v1_to_v2(
            copy.deepcopy(state),
        )
        assert new_state["reasoning_thread"] == ["existing"]
        assert any("already exists" in w for w in warnings)


# ── Multi-Step Migration ────────────────────────────────────────


class TestMultiStepMigration:
    """Tests for migrating across multiple versions."""

    def test_v1_to_v6_full_migration(self, migrator):
        state = _v1_state()
        result = migrator.migrate_state(state, target_version=6)
        assert result.success is True
        assert result.from_version == 1
        assert result.to_version == 6
        assert "reasoning_thread" in result.state_after
        assert "reflexion_trace" in result.state_after
        assert "technique_token_budget" in result.state_after
        assert "signals" in result.state_after
        assert result.state_after["_version"] == 6

    def test_v1_to_v3_partial_migration(self, migrator):
        state = _v1_state()
        result = migrator.migrate_state(state, target_version=3)
        assert result.success is True
        assert result.state_after["_version"] == 3
        assert "reasoning_thread" in result.state_after
        assert "reflexion_trace" in result.state_after
        assert "technique_token_budget" not in result.state_after

    def test_v3_to_v6_partial_migration(self, migrator):
        state = _v3_state()
        result = migrator.migrate_state(state, target_version=6)
        assert result.success is True
        assert result.state_after["_version"] == 6
        assert "signals" in result.state_after

    def test_v4_to_v5_with_int_gsd_state(self, migrator):
        state = _v4_state(gsd_state=3)
        result = migrator.migrate_state(state, target_version=5)
        assert result.success is True
        assert result.state_after["gsd_state"] == "reviewing"

    def test_all_changes_recorded_in_migration(self, migrator):
        # Use int gsd_state so v4->v5 produces a change
        state = _v1_state(gsd_state=3)
        result = migrator.migrate_state(state, target_version=6)
        assert len(result.changes_made) >= 5

    def test_migrate_to_latest_by_default(self, migrator):
        state = _v1_state()
        result = migrator.migrate_state(state)
        assert result.success is True
        assert result.to_version == 6


# ── Dry-Run Mode ────────────────────────────────────────────────


class TestDryRunMode:
    """Tests for dry-run (preview) mode."""

    def test_dry_run_does_not_modify_original(self, migrator):
        state = _v1_state()
        original_gsd = state["gsd_state"]
        result = migrator.migrate_state(
            state,
            target_version=6,
            dry_run=True,
        )
        # Original state should be unchanged
        assert state.get("gsd_state") == original_gsd
        assert "reasoning_thread" not in state
        # But result should show what would happen
        assert "reasoning_thread" in result.state_after

    def test_dry_run_returns_changes_preview(self, migrator):
        state = _v1_state()
        result = migrator.migrate_state(
            state,
            target_version=6,
            dry_run=True,
        )
        assert len(result.changes_made) > 0
        assert result.success is True

    def test_dry_run_v2_to_v6(self, migrator):
        state = _v2_state()
        result = migrator.migrate_state(
            state,
            target_version=6,
            dry_run=True,
        )
        assert result.success is True
        assert "signals" in result.state_after
        assert "reflexion_trace" not in state  # unchanged

    def test_dry_run_original_state_unchanged(self, migrator):
        state = _v4_state(gsd_state=1)
        original = copy.deepcopy(state)
        migrator.migrate_state(
            state,
            target_version=6,
            dry_run=True,
        )
        assert state == original


# ── Backward Compatibility ──────────────────────────────────────


class TestBackwardCompatibility:
    """Tests for loading old format states."""

    def test_v1_state_without_version_field(self, migrator):
        """State without _version should be treated as v1."""
        state = {"query": "test", "gsd_state": "new"}
        result = migrator.migrate_state(state, target_version=6)
        assert result.success is True
        assert result.from_version == 1

    def test_v1_state_with_int_gsd_loads(self, migrator):
        """Old states with int gsd_state should migrate."""
        state = _v1_state(gsd_state=4)
        result = migrator.migrate_state(state, target_version=6)
        assert result.success is True
        assert result.state_after["gsd_state"] == "responded"

    def test_v4_state_migrates_to_latest(self, migrator):
        state = _v4_state()
        state["_version"] = 4
        result = migrator.migrate_state(state)
        assert result.success is True
        assert result.to_version == 6

    def test_partial_v5_state_gets_defaults(self, migrator):
        """v5 state with partial signals gets merged defaults."""
        state = _v5_state()
        state["signals"] = {"intent_confidence": 0.9}
        state["_version"] = 5
        result = migrator.migrate_state(state, target_version=6)
        assert result.success is True
        assert result.state_after["signals"]["intent_confidence"] == 0.9
        assert result.state_after["signals"]["urgency_level"] == "medium"

    def test_state_with_extra_fields_preserved(self, migrator):
        """Extra/unknown fields should be preserved through
        migration."""
        state = _v1_state(custom_field="should_remain")
        result = migrator.migrate_state(state, target_version=6)
        assert result.state_after.get("custom_field") == "should_remain"


# ── Migration Validation ────────────────────────────────────────


class TestMigrationValidation:
    """Tests for state validation after migration."""

    def test_validate_v1_state(self, migrator):
        state = _v1_state()
        result = migrator.validate_state(state, 1)
        assert result.valid is True

    def test_validate_v6_state(self, migrator):
        state = _v6_state()
        result = migrator.validate_state(state, 6)
        assert result.valid is True

    def test_validate_missing_required_field(self, migrator):
        state = {"query": "test"}  # missing gsd_state
        result = migrator.validate_state(state, 1)
        assert result.valid is False
        assert any("gsd_state" in e for e in result.errors)

    def test_validate_unknown_version(self, migrator):
        state = _v1_state()
        result = migrator.validate_state(state, 99)
        assert result.valid is False
        assert any("Unknown schema version" in e for e in result.errors)

    def test_validate_v6_missing_signals_keys(self, migrator):
        state = _v6_state()
        state["signals"] = {"intent_confidence": 0.0}
        result = migrator.validate_state(state, 6)
        assert result.valid is False
        assert any("signals missing" in e for e in result.errors)

    def test_validate_v6_signals_not_dict(self, migrator):
        state = _v6_state()
        state["signals"] = "invalid"
        result = migrator.validate_state(state, 6)
        assert result.valid is False
        assert any("signals must be a dict" in e for e in result.errors)

    def test_validate_v5_int_gsd_warning(self, migrator):
        state = _v5_state()
        state["gsd_state"] = 2
        result = migrator.validate_state(state, 5)
        assert result.valid is True
        assert any("expected string" in w for w in result.warnings)

    def test_validate_v4_no_signals_required(self, migrator):
        state = _v4_state()
        result = migrator.validate_state(state, 4)
        assert result.valid is True


# ── Batch Migration ─────────────────────────────────────────────


class TestBatchMigration:
    """Tests for batch migration of multiple states."""

    def test_batch_migrate_multiple_states(self, migrator):
        states = [_v1_state(), _v2_state(), _v3_state()]
        result = migrator.batch_migrate(states, target_version=6)
        assert result.total == 3
        assert result.migrated == 3
        assert result.failed == 0

    def test_batch_migrate_with_skipped(self, migrator):
        already_v6 = _v6_state()
        v1_state = _v1_state()
        result = migrator.batch_migrate(
            [already_v6, v1_state],
            target_version=6,
        )
        assert result.total == 2
        assert result.skipped == 1
        assert result.migrated == 1

    def test_batch_migrate_dry_run(self, migrator):
        states = [_v1_state()]
        result = migrator.batch_migrate(
            states,
            target_version=6,
            dry_run=True,
        )
        assert result.total == 1
        assert result.migrated == 1
        assert "reasoning_thread" not in states[0]

    def test_batch_empty_list(self, migrator):
        result = migrator.batch_migrate([], target_version=6)
        assert result.total == 0
        assert result.migrated == 0
        assert result.failed == 0

    def test_batch_migrate_preserves_per_state_results(self, migrator):
        states = [_v1_state(), _v3_state()]
        result = migrator.batch_migrate(states, target_version=6)
        assert len(result.results) == 2
        assert result.results[0].from_version == 1
        assert result.results[1].from_version == 3
        assert all(r.success for r in result.results)


# ── Migration Path Calculation ─────────────────────────────────


class TestMigrationPath:
    """Tests for migration path calculation."""

    def test_path_v1_to_v6(self, migrator):
        path = migrator.get_migration_path(1, 6)
        assert path == [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]

    def test_path_same_version(self, migrator):
        path = migrator.get_migration_path(3, 3)
        assert path == []

    def test_path_backward_raises(self, migrator):
        with pytest.raises(ValueError, match="Cannot migrate backwards"):
            migrator.get_migration_path(6, 1)

    def test_path_missing_migration_raises(self, migrator):
        with pytest.raises(ValueError, match="No migration registered"):
            migrator.get_migration_path(1, 99)

    def test_path_partial_v3_to_v5(self, migrator):
        path = migrator.get_migration_path(3, 5)
        assert path == [(3, 4), (4, 5)]


# ── Rollback Capability ─────────────────────────────────────────


class TestRollback:
    """Tests for state rollback functionality."""

    def test_rollback_v6_to_v5_removes_signals(self, migrator):
        state = _v6_state()
        result = migrator.rollback_state(state, target_version=5)
        assert result.success is True
        assert "signals" not in result.state_after
        assert result.state_after["_version"] == 5

    def test_rollback_v5_to_v4_converts_gsd_to_int(self, migrator):
        state = _v5_state(gsd_state="processing")
        result = migrator.rollback_state(state, target_version=4)
        assert result.success is True
        assert result.state_after["gsd_state"] == 2
        assert result.state_after["_version"] == 4

    def test_rollback_v4_to_v3_removes_token_budget(self, migrator):
        state = _v4_state()
        result = migrator.rollback_state(state, target_version=3)
        assert result.success is True
        assert "technique_token_budget" not in result.state_after

    def test_rollback_v3_to_v2_removes_reflexion(self, migrator):
        state = _v3_state()
        result = migrator.rollback_state(state, target_version=2)
        assert result.success is True
        assert "reflexion_trace" not in result.state_after

    def test_rollback_v2_to_v1_removes_reasoning(self, migrator):
        state = _v2_state()
        result = migrator.rollback_state(state, target_version=1)
        assert result.success is True
        assert "reasoning_thread" not in result.state_after

    def test_rollback_to_same_version(self, migrator):
        state = _v6_state()
        result = migrator.rollback_state(state, target_version=6)
        assert result.success is True
        assert any("Already at target" in c for c in result.changes_made)

    def test_rollback_forward_raises_error(self, migrator):
        state = _v3_state()
        result = migrator.rollback_state(state, target_version=6)
        assert result.success is False

    def test_rollback_dry_run(self, migrator):
        state = _v6_state()
        original = copy.deepcopy(state)
        migrator.rollback_state(
            state,
            target_version=5,
            dry_run=True,
        )
        assert state == original


# ── Unknown Version Handling ────────────────────────────────────


class TestUnknownVersion:
    """Tests for handling unknown or missing versions."""

    def test_migrate_from_unregistered_version(self, migrator):
        """No migration from v7 onwards — from > to is backward."""
        state = {"_version": 7, "query": "test", "gsd_state": "new"}
        result = migrator.migrate_state(state, target_version=6)
        assert result.success is False
        # from_version > target_version so path fails
        assert result.from_version == 7

    def test_migrate_to_unregistered_version(self, migrator):
        state = _v1_state()
        result = migrator.migrate_state(state, target_version=99)
        assert result.success is False
        assert any("No migration" in w for w in result.warnings)

    def test_register_additional_migration(self, migrator):
        def custom_migrate(state):
            state["custom_field"] = True
            state["_version"] = 7
            return state, ["Added custom_field"], []

        migrator.register_migration(6, 7, custom_migrate)
        state = _v6_state()
        result = migrator.migrate_state(state, target_version=7)
        assert result.success is True
        assert result.state_after["custom_field"] is True

    def test_register_invalid_migration_raises(self, migrator):
        def noop(state):
            return state, [], []

        with pytest.raises(ValueError, match="less than"):
            migrator.register_migration(5, 5, noop)
        with pytest.raises(ValueError, match="less than"):
            migrator.register_migration(6, 5, noop)


# ── Already-at-Target Version ───────────────────────────────────


class TestAlreadyAtTarget:
    """Tests for states already at the target version."""

    def test_already_at_latest(self, migrator):
        state = _v6_state()
        result = migrator.migrate_state(state)
        assert result.success is True
        assert result.to_version == 6
        assert any("Already at target" in c for c in result.changes_made)

    def test_already_at_specific_target(self, migrator):
        state = _v3_state()
        result = migrator.migrate_state(state, target_version=3)
        assert result.success is True
        assert result.to_version == 3

    def test_already_at_target_returns_same_state(self, migrator):
        state = _v6_state()
        result = migrator.migrate_state(state, target_version=6)
        assert result.state_after == state


# ── Missing Field Defaults ──────────────────────────────────────


class TestMissingFieldDefaults:
    """Tests for default value filling on new fields."""

    def test_v1_to_v2_default_is_empty_list(self, migrator):
        state = _v1_state()
        result = migrator.migrate_state(state, target_version=2)
        assert result.state_after["reasoning_thread"] == []

    def test_v2_to_v3_default_is_none(self, migrator):
        state = _v2_state()
        result = migrator.migrate_state(state, target_version=3)
        assert result.state_after["reflexion_trace"] is None

    def test_v3_to_v4_default_is_1500(self, migrator):
        state = _v3_state()
        result = migrator.migrate_state(state, target_version=4)
        assert result.state_after["technique_token_budget"] == 1500

    def test_v5_to_v6_signal_defaults(self, migrator):
        state = _v5_state()
        result = migrator.migrate_state(state, target_version=6)
        signals = result.state_after["signals"]
        assert signals["intent_confidence"] == 0.0
        assert signals["urgency_level"] == "medium"
        assert signals["sentiment_score"] == 0.0
        assert signals["language_code"] == "en"


# ── Registry and Metadata ───────────────────────────────────────


class TestRegistryAndMetadata:
    """Tests for migration registry and metadata methods."""

    def test_get_latest_version(self, migrator):
        assert migrator.get_latest_version() == 6

    def test_list_registered_migrations(self, migrator):
        migrations = migrator.list_registered_migrations()
        assert (1, 2) in migrations
        assert (5, 6) in migrations
        assert len(migrations) == 5

    def test_custom_latest_version(self):
        m = StateMigrator(latest_version=3)
        assert m.get_latest_version() == 3

    def test_batch_result_structure(self, migrator):
        states = [_v1_state()]
        result = migrator.batch_migrate(states)
        assert isinstance(result, BatchMigrationResult)
        assert result.total == 1
        assert isinstance(result.results[0], MigrationResult)

    def test_migration_result_structure(self, migrator):
        state = _v1_state()
        result = migrator.migrate_state(state)
        assert isinstance(result, MigrationResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.changes_made, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.state_after, dict)

    def test_validation_result_structure(self, migrator):
        result = migrator.validate_state(_v1_state(), 1)
        assert isinstance(result, ValidationResult)
        assert isinstance(result.valid, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert result.version == 1
