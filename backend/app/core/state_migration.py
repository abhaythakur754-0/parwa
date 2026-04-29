"""
State Migration Tooling (Week 10 Day 3).

Migrates conversation state between schema versions with:
  - Forward migration (v1 -> v2 -> v3 ... v6)
  - Backward compatibility (load old, save new)
  - Migration registry pattern
  - Dry-run mode (preview without applying)
  - Rollback support
  - Migration logging
  - Batch migration
  - State validation after migration
  - Default value filling for new fields

Architecture:
  - Migration functions are registered with register_migration()
  - Each function transforms a state dict and returns changes made
  - The migrator chains migrations to reach a target version
  - Validation runs after every migration step

Usage:
    from app.core.state_migration import StateMigrator

    migrator = StateMigrator()
    result = migrator.migrate_state(state_dict, target_version=6)
"""

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("state_migration")


# ── Data Classes ────────────────────────────────────────────────


@dataclass
class MigrationResult:
    """Result of a single state migration."""

    success: bool
    from_version: int
    to_version: int
    changes_made: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    state_after: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchMigrationResult:
    """Result of a batch migration operation."""

    total: int
    migrated: int
    failed: int
    skipped: int
    results: List[MigrationResult] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of state validation against a schema version."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    version: int = 0


# ── Migration Function Type ────────────────────────────────────

MigrationFn = Callable[
    [Dict[str, Any]],
    Tuple[Dict[str, Any], List[str], List[str]],
]


# ── Pre-registered Migrations ──────────────────────────────────


def _migrate_v1_to_v2(
    state: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """v1 -> v2: Add reasoning_thread field (default [])."""
    changes: List[str] = []
    warnings: List[str] = []

    if "reasoning_thread" not in state:
        state["reasoning_thread"] = []
        changes.append("Added reasoning_thread field (default [])")
    else:
        warnings.append("reasoning_thread already exists, not overwritten")

    state["_version"] = 2
    return state, changes, warnings


def _migrate_v2_to_v3(
    state: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """v2 -> v3: Add reflexion_trace field (default None)."""
    changes: List[str] = []
    warnings: List[str] = []

    if "reflexion_trace" not in state:
        state["reflexion_trace"] = None
        changes.append("Added reflexion_trace field (default None)")
    else:
        warnings.append("reflexion_trace already exists, not overwritten")

    state["_version"] = 3
    return state, changes, warnings


def _migrate_v3_to_v4(
    state: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """v3 -> v4: Add technique_token_budget field (default 1500)."""
    changes: List[str] = []
    warnings: List[str] = []

    if "technique_token_budget" not in state:
        state["technique_token_budget"] = 1500
        changes.append("Added technique_token_budget field (default 1500)")
    else:
        warnings.append("technique_token_budget already exists, " "not overwritten")

    state["_version"] = 4
    return state, changes, warnings


def _migrate_v4_to_v5(
    state: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """v4 -> v5: Convert gsd_state from int to string enum.

    Converts integer GSD state values to their string enum
    equivalents: 0='new', 1='classifying', 2='processing',
    3='reviewing', 4='responded', 5='closed'.
    """
    changes: List[str] = []
    warnings: List[str] = []

    GSD_INT_TO_STR = {
        0: "new",
        1: "classifying",
        2: "processing",
        3: "reviewing",
        4: "responded",
        5: "closed",
    }

    gsd = state.get("gsd_state")
    if isinstance(gsd, int):
        new_val = GSD_INT_TO_STR.get(gsd)
        if new_val:
            state["gsd_state"] = new_val
            changes.append(
                f"Converted gsd_state from int {gsd} " f"to string '{new_val}'"
            )
        else:
            warnings.append(
                f"Unknown gsd_state int value: {gsd}, " "falling back to 'new'"
            )
            state["gsd_state"] = "new"
            changes.append(f"Converted gsd_state from int {gsd} " "to fallback 'new'")
    elif isinstance(gsd, str):
        warnings.append("gsd_state is already a string, skipping conversion")
    else:
        warnings.append(
            "gsd_state has unexpected type " f"{type(gsd).__name__}, setting to 'new'"
        )
        state["gsd_state"] = "new"
        changes.append(f"Set gsd_state to 'new' (was {type(gsd).__name__})")

    state["_version"] = 5
    return state, changes, warnings


def _migrate_v5_to_v6(
    state: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """v5 -> v6: Add signals sub-object with defaults.

    Adds a 'signals' dict with default values for
    intent_confidence, urgency_level, sentiment_score,
    and language_code.
    """
    changes: List[str] = []
    warnings: List[str] = []

    default_signals = {
        "intent_confidence": 0.0,
        "urgency_level": "medium",
        "sentiment_score": 0.0,
        "language_code": "en",
    }

    if "signals" not in state:
        state["signals"] = copy.deepcopy(default_signals)
        changes.append(
            "Added signals sub-object with defaults "
            "(intent_confidence=0.0, urgency_level='medium', "
            "sentiment_score=0.0, language_code='en')"
        )
    else:
        # Merge missing keys into existing signals
        if isinstance(state["signals"], dict):
            merged = False
            for key, val in default_signals.items():
                if key not in state["signals"]:
                    state["signals"][key] = val
                    merged = True
            if merged:
                changes.append(
                    "Merged missing keys into existing " "signals sub-object"
                )
            else:
                warnings.append("signals already has all expected keys")
        else:
            warnings.append(
                "signals has unexpected type "
                f"{type(state['signals']).__name__}, "
                "replacing with defaults"
            )
            state["signals"] = copy.deepcopy(default_signals)
            changes.append("Replaced invalid signals with defaults")

    state["_version"] = 6
    return state, changes, warnings


# ── Version Schemas for Validation ─────────────────────────────

# Required fields per version
_VERSION_REQUIRED_FIELDS: Dict[int, List[str]] = {
    1: ["query", "gsd_state"],
    2: ["query", "gsd_state", "reasoning_thread"],
    3: ["query", "gsd_state", "reasoning_thread", "reflexion_trace"],
    4: [
        "query",
        "gsd_state",
        "reasoning_thread",
        "reflexion_trace",
        "technique_token_budget",
    ],
    5: [
        "query",
        "gsd_state",
        "reasoning_thread",
        "reflexion_trace",
        "technique_token_budget",
    ],
    6: [
        "query",
        "gsd_state",
        "reasoning_thread",
        "reflexion_trace",
        "technique_token_budget",
        "signals",
    ],
}

# Required keys within signals sub-object for v6
_SIGNALS_REQUIRED_KEYS = [
    "intent_confidence",
    "urgency_level",
    "sentiment_score",
    "language_code",
]


# ── StateMigrator ───────────────────────────────────────────────


class StateMigrator:
    """State migration engine with registry pattern.

    Manages forward migrations between schema versions with
    validation, dry-run support, and batch processing.

    Args:
        latest_version: The current latest schema version.
            Defaults to 6.
    """

    def __init__(self, latest_version: int = 6) -> None:
        """Initialize the migrator and pre-register migrations.

        Args:
            latest_version: The latest supported schema version.
        """
        self._latest_version = latest_version

        # Registry: (from_version, to_version) -> migration_fn
        self._registry: Dict[Tuple[int, int], MigrationFn] = {}

        # Rollback stack: (from_version, to_version) ->
        #   reverse_fn (swaps the migration)
        self._rollback_registry: Dict[Tuple[int, int], MigrationFn] = {}

        # Pre-register the built-in migrations
        self.register_migration(1, 2, _migrate_v1_to_v2)
        self.register_migration(2, 3, _migrate_v2_to_v3)
        self.register_migration(3, 4, _migrate_v3_to_v4)
        self.register_migration(4, 5, _migrate_v4_to_v5)
        self.register_migration(5, 6, _migrate_v5_to_v6)

        # Build reverse (rollback) migrations
        self._build_rollback_registry()

    # ── Registry ────────────────────────────────────────────────

    def register_migration(
        self,
        from_version: int,
        to_version: int,
        migrate_fn: MigrationFn,
    ) -> None:
        """Register a migration function.

        Args:
            from_version: Source schema version.
            to_version: Target schema version.
            migrate_fn: Function that takes a state dict
                and returns (new_state, changes, warnings).

        Raises:
            ValueError: If from_version >= to_version.
        """
        if from_version >= to_version:
            raise ValueError(
                f"from_version ({from_version}) must be "
                f"less than to_version ({to_version})"
            )

        self._registry[(from_version, to_version)] = migrate_fn

        logger.info(
            "migration_registered",
            extra={
                "from": from_version,
                "to": to_version,
            },
        )

    def _build_rollback_registry(self) -> None:
        """Build rollback (reverse) migration functions.

        Creates simple reverse functions that restore the
        state by removing fields added during forward
        migration.
        """
        # v2->v1: remove reasoning_thread
        self._rollback_registry[(2, 1)] = self._make_rollback(
            1,
            remove_keys=["reasoning_thread"],
        )
        # v3->v2: remove reflexion_trace
        self._rollback_registry[(3, 2)] = self._make_rollback(
            2,
            remove_keys=["reflexion_trace"],
        )
        # v4->v3: remove technique_token_budget
        self._rollback_registry[(4, 3)] = self._make_rollback(
            3,
            remove_keys=["technique_token_budget"],
        )
        # v5->v4: revert gsd_state string back to int
        self._rollback_registry[(5, 4)] = self._rollback_v5_to_v4
        # v6->v5: remove signals
        self._rollback_registry[(6, 5)] = self._make_rollback(
            5,
            remove_keys=["signals"],
        )

    @staticmethod
    def _make_rollback(
        target_version: int,
        remove_keys: List[str],
    ) -> MigrationFn:
        """Create a rollback function that removes fields.

        Args:
            target_version: Version to set after rollback.
            remove_keys: Fields to remove from state.

        Returns:
            Rollback migration function.
        """

        def _rollback(
            state: Dict[str, Any],
        ) -> Tuple[Dict[str, Any], List[str], List[str]]:
            changes: List[str] = []
            warnings: List[str] = []
            for key in remove_keys:
                if key in state:
                    del state[key]
                    changes.append(f"Removed field '{key}' during rollback")
                else:
                    warnings.append(f"Field '{key}' not found during rollback")
            state["_version"] = target_version
            return state, changes, warnings

        return _rollback

    @staticmethod
    def _rollback_v5_to_v4(
        state: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Rollback v5->v4: convert gsd_state back to int."""
        changes: List[str] = []
        warnings: List[str] = []

        GSD_STR_TO_INT = {
            "new": 0,
            "classifying": 1,
            "processing": 2,
            "reviewing": 3,
            "responded": 4,
            "closed": 5,
        }

        gsd = state.get("gsd_state")
        if isinstance(gsd, str):
            int_val = GSD_STR_TO_INT.get(gsd)
            if int_val is not None:
                state["gsd_state"] = int_val
                changes.append(
                    f"Rolled back gsd_state from '{gsd}' " f"to int {int_val}"
                )
            else:
                warnings.append(
                    f"Unknown gsd_state string '{gsd}', " "falling back to 0"
                )
                state["gsd_state"] = 0
                changes.append("Rolled back gsd_state to fallback int 0")
        elif isinstance(gsd, int):
            warnings.append("gsd_state is already an int, skipping")
        else:
            state["gsd_state"] = 0
            changes.append("Set gsd_state to int 0 during rollback")

        state["_version"] = 4
        return state, changes, warnings

    # ── Migration Path ──────────────────────────────────────────

    def get_migration_path(
        self,
        from_version: int,
        to_version: int,
    ) -> List[Tuple[int, int]]:
        """Calculate the migration path between two versions.

        Only forward migration paths are supported.
        The path is a sequence of (from, to) version pairs.

        Args:
            from_version: Starting version.
            to_version: Target version.

        Returns:
            List of (from, to) version tuples.

        Raises:
            ValueError: If no path exists.
        """
        if from_version == to_version:
            return []

        if from_version > to_version:
            raise ValueError(
                "Cannot migrate backwards from "
                f"v{from_version} to v{to_version}. "
                "Use rollback instead."
            )

        path: List[Tuple[int, int]] = []
        current = from_version
        while current < to_version:
            step = (current, current + 1)
            if step not in self._registry:
                raise ValueError(
                    "No migration registered for step " f"v{current} -> v{current + 1}"
                )
            path.append(step)
            current += 1

        return path

    # ── Single State Migration ──────────────────────────────────

    def migrate_state(
        self,
        state_dict: Dict[str, Any],
        target_version: Optional[int] = None,
        dry_run: bool = False,
    ) -> MigrationResult:
        """Migrate a single state dict to a target version.

        Args:
            state_dict: The state dictionary to migrate.
            target_version: Target schema version.
                Defaults to latest_version.
            dry_run: If True, preview changes without
                modifying the original state.

        Returns:
            MigrationResult with success status and details.
        """
        if target_version is None:
            target_version = self._latest_version

        # Determine current version
        from_version = state_dict.get("_version", 1)

        # Already at target
        if from_version == target_version:
            return MigrationResult(
                success=True,
                from_version=from_version,
                to_version=target_version,
                changes_made=["Already at target version"],
                warnings=[],
                state_after=copy.deepcopy(state_dict),
            )

        # Validate source state
        validation = self.validate_state(state_dict, from_version)
        if not validation.valid:
            return MigrationResult(
                success=False,
                from_version=from_version,
                to_version=target_version,
                changes_made=[],
                warnings=validation.warnings,
                state_after=copy.deepcopy(state_dict),
            )

        # Get migration path
        try:
            path = self.get_migration_path(
                from_version,
                target_version,
            )
        except ValueError as exc:
            return MigrationResult(
                success=False,
                from_version=from_version,
                to_version=target_version,
                changes_made=[],
                warnings=[str(exc)],
                state_after=copy.deepcopy(state_dict),
            )

        # Work on a copy for dry-run
        working = copy.deepcopy(state_dict) if dry_run else state_dict

        all_changes: List[str] = []
        all_warnings: List[str] = []
        success = True

        for from_v, to_v in path:
            migrate_fn = self._registry[(from_v, to_v)]
            try:
                working, changes, warnings = migrate_fn(working)
                all_changes.extend(changes)
                all_warnings.extend(warnings)

                # Validate after each step (unless dry-run
                # where we just continue)
                if not dry_run:
                    step_val = self.validate_state(
                        working,
                        to_v,
                    )
                    if not step_val.valid:
                        all_warnings.append(
                            "Validation warning after "
                            f"v{from_v}->v{to_v}: "
                            f"{step_val.errors}"
                        )

            except Exception as exc:
                success = False
                all_warnings.append(f"Migration v{from_v}->v{to_v} failed: " f"{exc}")
                logger.error(
                    "migration_step_failed",
                    extra={
                        "from": from_v,
                        "to": to_v,
                        "error": str(exc),
                    },
                )
                break

        return MigrationResult(
            success=success,
            from_version=from_version,
            to_version=(target_version if success else from_version),
            changes_made=all_changes,
            warnings=all_warnings,
            state_after=copy.deepcopy(working),
        )

    # ── Rollback ────────────────────────────────────────────────

    def rollback_state(
        self,
        state_dict: Dict[str, Any],
        target_version: int,
        dry_run: bool = False,
    ) -> MigrationResult:
        """Rollback a state dict to an earlier version.

        Args:
            state_dict: The state dictionary to rollback.
            target_version: Target (lower) schema version.
            dry_run: If True, preview without applying.

        Returns:
            MigrationResult with success status and details.
        """
        from_version = state_dict.get("_version", 1)

        if from_version == target_version:
            return MigrationResult(
                success=True,
                from_version=from_version,
                to_version=target_version,
                changes_made=["Already at target version"],
                warnings=[],
                state_after=copy.deepcopy(state_dict),
            )

        if from_version < target_version:
            return MigrationResult(
                success=False,
                from_version=from_version,
                to_version=target_version,
                changes_made=[],
                warnings=["Rollback target must be lower than " "current version"],
                state_after=copy.deepcopy(state_dict),
            )

        # Build rollback path: step down one version at a time
        path: List[Tuple[int, int]] = []
        current = from_version
        while current > target_version:
            step = (current, current - 1)
            if step not in self._rollback_registry:
                return MigrationResult(
                    success=False,
                    from_version=from_version,
                    to_version=target_version,
                    changes_made=[],
                    warnings=[
                        "No rollback registered for step " f"v{current}->v{current - 1}"
                    ],
                    state_after=copy.deepcopy(state_dict),
                )
            path.append(step)
            current -= 1

        working = copy.deepcopy(state_dict) if dry_run else state_dict

        all_changes: List[str] = []
        all_warnings: List[str] = []
        success = True

        for from_v, to_v in path:
            rollback_fn = self._rollback_registry[(from_v, to_v)]
            try:
                working, changes, warnings = rollback_fn(working)
                all_changes.extend(changes)
                all_warnings.extend(warnings)
            except Exception as exc:
                success = False
                all_warnings.append(f"Rollback v{from_v}->v{to_v} failed: " f"{exc}")
                break

        return MigrationResult(
            success=success,
            from_version=from_version,
            to_version=(target_version if success else from_version),
            changes_made=all_changes,
            warnings=all_warnings,
            state_after=copy.deepcopy(working),
        )

    # ── Validation ──────────────────────────────────────────────

    def validate_state(
        self,
        state_dict: Dict[str, Any],
        version: int,
    ) -> ValidationResult:
        """Validate a state dict against a schema version.

        Checks required fields exist and have correct types.

        Args:
            state_dict: State to validate.
            version: Schema version to validate against.

        Returns:
            ValidationResult with errors and warnings.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if version not in _VERSION_REQUIRED_FIELDS:
            errors.append(f"Unknown schema version: {version}")
            return ValidationResult(
                valid=False,
                errors=errors,
                version=version,
            )

        required = _VERSION_REQUIRED_FIELDS[version]
        for field_name in required:
            if field_name not in state_dict:
                errors.append(f"Missing required field: {field_name}")

        # Type checks for specific versions
        if version >= 5:
            gsd = state_dict.get("gsd_state")
            if isinstance(gsd, int) and gsd is not None:
                warnings.append(
                    "gsd_state is an int; expected string " f"(in v{version})"
                )

        if version >= 6 and "signals" in state_dict:
            signals = state_dict["signals"]
            if not isinstance(signals, dict):
                errors.append("signals must be a dict")
            else:
                for key in _SIGNALS_REQUIRED_KEYS:
                    if key not in signals:
                        errors.append(f"signals missing key: {key}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            version=version,
        )

    # ── Batch Migration ─────────────────────────────────────────

    def batch_migrate(
        self,
        states: List[Dict[str, Any]],
        target_version: Optional[int] = None,
        dry_run: bool = False,
    ) -> BatchMigrationResult:
        """Migrate multiple states to a target version.

        Args:
            states: List of state dictionaries.
            target_version: Target schema version.
                Defaults to latest_version.
            dry_run: If True, preview without applying.

        Returns:
            BatchMigrationResult with per-state results.
        """
        if target_version is None:
            target_version = self._latest_version

        results: List[MigrationResult] = []
        migrated = 0
        failed = 0
        skipped = 0

        for state in states:
            result = self.migrate_state(
                state,
                target_version,
                dry_run,
            )
            results.append(result)

            if result.success:
                if (
                    len(result.changes_made) == 1
                    and "Already at target" in result.changes_made[0]
                ):
                    skipped += 1
                else:
                    migrated += 1
            else:
                failed += 1

        return BatchMigrationResult(
            total=len(states),
            migrated=migrated,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    # ── Latest Version ──────────────────────────────────────────

    def get_latest_version(self) -> int:
        """Get the latest supported schema version.

        Returns:
            Latest version number.
        """
        return self._latest_version

    def list_registered_migrations(self) -> List[Tuple[int, int]]:
        """List all registered migration steps.

        Returns:
            Sorted list of (from, to) version tuples.
        """
        return sorted(self._registry.keys())
