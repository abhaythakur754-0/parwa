"""
SG-21: Task Decomposition Service.

Manages feature-level task decompositions for the Phase 3 AI Engine
build process. Tracks sub-tasks, dependencies, agent assignments,
and status for each feature.

Storage: JSON file at documents/phase3_task_decomposition.json
as the backing store. The service provides an in-memory cache
that reads from and writes to the JSON file.

BC-012: All errors use ParwaBaseError.
"""

import copy
import json
import os
from dataclasses import dataclass, field
from typing import Optional

from app.exceptions import (
    NotFoundError,
    ValidationError,
)

# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_SUBTASK_STATUSES = {
    "pending",
    "in_progress",
    "blocked",
    "completed",
    "skipped",
}

DEFAULT_JSON_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "documents",
    "phase3_task_decomposition.json",
)

_DATA_KEY = "decompositions"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class SubTask:
    """A single sub-task within a feature decomposition."""

    task_id: str
    name: str
    estimate_hours: float
    dependencies: list[str] = field(default_factory=list)
    agent: str = ""
    status: str = "pending"


@dataclass
class TaskDecomposition:
    """A feature's complete decomposition into sub-tasks."""

    feature_id: str
    feature_name: str
    sub_tasks: list[SubTask] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "sub_tasks": [
                {
                    "task_id": st.task_id,
                    "name": st.name,
                    "estimate_hours": st.estimate_hours,
                    "dependencies": list(st.dependencies),
                    "agent": st.agent,
                    "status": st.status,
                }
                for st in self.sub_tasks
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskDecomposition":
        """Deserialize from dict."""
        sub_tasks = []
        for st_data in data.get("sub_tasks", []):
            sub_tasks.append(
                SubTask(
                    task_id=st_data["task_id"],
                    name=st_data["name"],
                    estimate_hours=float(
                        st_data.get("estimate_hours", 0),
                    ),
                    dependencies=list(
                        st_data.get("dependencies", []),
                    ),
                    agent=st_data.get("agent", ""),
                    status=st_data.get("status", "pending"),
                )
            )
        return cls(
            feature_id=data["feature_id"],
            feature_name=data["feature_name"],
            sub_tasks=sub_tasks,
        )


# ══════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════


def _validate_feature_id(feature_id: str) -> None:
    """Validate feature_id is non-empty."""
    if not feature_id or not isinstance(feature_id, str):
        raise ValidationError(
            message="feature_id is required and must be a string",
        )
    if not feature_id.strip():
        raise ValidationError(
            message="feature_id cannot be empty or whitespace",
        )


def _validate_feature_name(feature_name: str) -> None:
    """Validate feature_name is non-empty."""
    if (
        not feature_name
        or not isinstance(feature_name, str)
        or not feature_name.strip()
    ):
        raise ValidationError(
            message=("feature_name is required and cannot be empty"),
        )


def _validate_sub_tasks(
    sub_tasks: list,
    existing_task_ids: Optional[set] = None,
) -> None:
    """Validate sub_tasks list structure."""
    if not isinstance(sub_tasks, list):
        raise ValidationError(
            message="sub_tasks must be a list",
        )
    if existing_task_ids is None:
        existing_task_ids = set()
    seen_ids = set()
    for i, st in enumerate(sub_tasks):
        if not isinstance(st, dict):
            raise ValidationError(
                message=(f"sub_tasks[{i}] must be a dict"),
            )
        # task_id
        if "task_id" not in st:
            raise ValidationError(
                message=(f"sub_tasks[{i}] missing 'task_id'"),
            )
        tid = st["task_id"]
        if not isinstance(tid, str) or not tid.strip():
            raise ValidationError(
                message=(f"sub_tasks[{i}] task_id must be a " "non-empty string"),
            )
        if tid in seen_ids:
            raise ValidationError(
                message=(f"Duplicate task_id '{tid}' in sub_tasks"),
            )
        seen_ids.add(tid)
        # name
        if "name" not in st:
            raise ValidationError(
                message=(f"sub_tasks[{i}] missing 'name'"),
            )
        if not isinstance(st["name"], str) or not st["name"].strip():
            raise ValidationError(
                message=(f"sub_tasks[{i}] name must be a " "non-empty string"),
            )
        # estimate_hours
        hours = st.get("estimate_hours", 0)
        try:
            h = float(hours)
            if h < 0:
                raise ValidationError(
                    message=(f"sub_tasks[{i}] estimate_hours " "cannot be negative"),
                )
        except (TypeError, ValueError):
            raise ValidationError(
                message=(f"sub_tasks[{i}] estimate_hours must " "be a number"),
            )
        # dependencies
        deps = st.get("dependencies", [])
        if not isinstance(deps, list):
            raise ValidationError(
                message=(f"sub_tasks[{i}] dependencies must be " "a list"),
            )
        for dep in deps:
            if not isinstance(dep, str) or not dep.strip():
                raise ValidationError(
                    message=(
                        f"sub_tasks[{i}] each dependency " "must be a non-empty string"
                    ),
                )
        # status
        status = st.get("status", "pending")
        if status not in VALID_SUBTASK_STATUSES:
            raise ValidationError(
                message=(
                    f"sub_tasks[{i}] invalid status "
                    f"'{status}'. Must be one of: "
                    f"{', '.join(sorted(VALID_SUBTASK_STATUSES))}"
                ),
            )
        # agent (optional, can be empty string)
        agent = st.get("agent", "")
        if not isinstance(agent, str):
            raise ValidationError(
                message=(f"sub_tasks[{i}] agent must be a string"),
            )


def _validate_status(status: str) -> None:
    """Validate a status transition value."""
    if status not in VALID_SUBTASK_STATUSES:
        raise ValidationError(
            message=(
                f"Invalid status '{status}'. Must be one of: "
                f"{', '.join(sorted(VALID_SUBTASK_STATUSES))}"
            ),
        )


def _validate_task_id(task_id: str) -> None:
    """Validate task_id is non-empty."""
    if not task_id or not isinstance(task_id, str):
        raise ValidationError(
            message="task_id is required and must be a string",
        )
    if not task_id.strip():
        raise ValidationError(
            message="task_id cannot be empty or whitespace",
        )


def _validate_agent_name(agent_name: Optional[str]) -> None:
    """Validate agent_name filter (can be None for no filter)."""
    if agent_name is not None:
        if not isinstance(agent_name, str) or not agent_name.strip():
            raise ValidationError(
                message="agent_name must be a non-empty string",
            )


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class TaskDecompositionService:
    """
    Service for managing Phase 3 task decompositions.

    Loads from and persists to a JSON file. All query operations
    work on in-memory data. Call save() to persist changes.
    """

    def __init__(self, json_path: Optional[str] = None):
        """
        Initialize the service.

        Args:
            json_path: Path to the JSON backing store.
                       Defaults to
                       documents/phase3_task_decomposition.json
        """
        if json_path is None:
            json_path = DEFAULT_JSON_PATH
        self._json_path = json_path
        self._decompositions: dict[str, TaskDecomposition] = {}
        self._load()

    def _load(self) -> None:
        """Load decompositions from the JSON file."""
        if not os.path.exists(self._json_path):
            self._decompositions = {}
            return
        try:
            with open(self._json_path, "r") as f:
                raw = json.load(f)
            data = raw.get(_DATA_KEY, {})
            if not isinstance(data, dict):
                self._decompositions = {}
                return
            for fid, fdata in data.items():
                if isinstance(fdata, dict):
                    self._decompositions[fid] = TaskDecomposition.from_dict(fdata)
        except (json.JSONDecodeError, OSError, KeyError):
            self._decompositions = {}

    def save(self) -> None:
        """Persist decompositions to the JSON file."""
        # Ensure parent directory exists
        parent = os.path.dirname(self._json_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        data = {fid: decomp.to_dict() for fid, decomp in self._decompositions.items()}
        with open(self._json_path, "w") as f:
            json.dump({_DATA_KEY: data}, f, indent=2)

    # ── CRUD Operations ──────────────────────────────────────────

    def register_task_decomposition(
        self,
        feature_id: str,
        feature_name: str,
        sub_tasks: list[dict],
    ) -> TaskDecomposition:
        """
        Register a feature's decomposition.

        Args:
            feature_id: Unique feature identifier (e.g. "SG-21")
            feature_name: Human-readable feature name
            sub_tasks: List of sub-task dicts with keys:
                task_id, name, estimate_hours, dependencies,
                agent, status

        Returns:
            The created TaskDecomposition.

        Raises:
            ValidationError: If inputs are invalid.
            ValidationError: If feature_id already exists.
        """
        _validate_feature_id(feature_id)
        _validate_feature_name(feature_name)
        _validate_sub_tasks(sub_tasks)

        fid = feature_id.strip()

        if fid in self._decompositions:
            raise ValidationError(
                message=(
                    f"Feature '{fid}' already has a "
                    "decomposition. Use update instead."
                ),
            )

        decomp = TaskDecomposition(
            feature_id=fid,
            feature_name=feature_name.strip(),
            sub_tasks=[
                SubTask(
                    task_id=st["task_id"].strip(),
                    name=st["name"].strip(),
                    estimate_hours=float(
                        st.get("estimate_hours", 0),
                    ),
                    dependencies=[
                        d.strip()
                        for d in st.get(
                            "dependencies",
                            [],
                        )
                    ],
                    agent=st.get("agent", "").strip(),
                    status=st.get("status", "pending").strip(),
                )
                for st in sub_tasks
            ],
        )
        self._decompositions[fid] = decomp
        return decomp

    def get_decomposition(
        self,
        feature_id: str,
    ) -> Optional[TaskDecomposition]:
        """
        Get a feature's decomposition.

        Returns None if not found.
        """
        _validate_feature_id(feature_id)
        return self._decompositions.get(feature_id.strip())

    def list_decompositions(
        self,
        agent_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[TaskDecomposition]:
        """
        List all decompositions, optionally filtered.

        Args:
            agent_name: Filter by agent name (sub-task agent).
            status: Filter by sub-task status.

        Returns:
            List of matching TaskDecomposition objects.
            If filters are provided, returns only decompositions
            that have at least one matching sub-task.
        """
        _validate_agent_name(agent_name)
        if status is not None:
            _validate_status(status)

        results: list[TaskDecomposition] = []

        for decomp in self._decompositions.values():
            filtered = copy.deepcopy(decomp)
            matching = []

            for st in filtered.sub_tasks:
                if agent_name is not None:
                    if st.agent != agent_name.strip():
                        continue
                if status is not None:
                    if st.status != status:
                        continue
                matching.append(st)

            if agent_name is not None or status is not None:
                if not matching:
                    continue
                filtered.sub_tasks = matching

            results.append(filtered)

        return results

    def update_subtask_status(
        self,
        feature_id: str,
        task_id: str,
        status: str,
    ) -> SubTask:
        """
        Update a sub-task's status.

        Args:
            feature_id: Feature identifier.
            task_id: Sub-task identifier.
            status: New status value.

        Returns:
            The updated SubTask.

        Raises:
            ValidationError: If inputs are invalid.
            NotFoundError: If feature or sub-task not found.
        """
        _validate_feature_id(feature_id)
        _validate_task_id(task_id)
        _validate_status(status)

        fid = feature_id.strip()
        tid = task_id.strip()

        decomp = self._decompositions.get(fid)
        if decomp is None:
            raise NotFoundError(
                message=(f"Feature '{fid}' not found"),
            )

        for st in decomp.sub_tasks:
            if st.task_id == tid:
                st.status = status
                return st

        raise NotFoundError(
            message=(f"Sub-task '{tid}' not found in feature " f"'{fid}'"),
        )

    def get_agent_workload(self, agent_name: str) -> dict:
        """
        Get workload summary for an agent.

        Returns all tasks assigned to the agent with status counts.

        Args:
            agent_name: Agent name to filter by.

        Returns:
            Dict with:
                agent_name, total_tasks, sub_tasks (list),
                status_counts (dict), total_hours.
        """
        _validate_agent_name(agent_name)
        agent = agent_name.strip() if agent_name else ""

        sub_tasks: list[SubTask] = []
        for decomp in self._decompositions.values():
            for st in decomp.sub_tasks:
                if st.agent == agent:
                    sub_tasks.append(st)

        status_counts: dict[str, int] = {}
        total_hours = 0.0
        for st in sub_tasks:
            status_counts[st.status] = status_counts.get(st.status, 0) + 1
            total_hours += st.estimate_hours

        return {
            "agent_name": agent,
            "total_tasks": len(sub_tasks),
            "sub_tasks": sub_tasks,
            "status_counts": status_counts,
            "total_hours": round(total_hours, 2),
        }

    def get_blocked_tasks(self) -> list[dict]:
        """
        Get all blocked tasks or tasks whose dependencies
        are not completed.

        Returns:
            List of dicts with:
                feature_id, feature_name, task_id, task_name,
                agent, status, unmet_dependencies.
        """
        # Build a global map of task_id -> status
        task_status_map: dict[str, str] = {}
        for decomp in self._decompositions.values():
            for st in decomp.sub_tasks:
                task_status_map[st.task_id] = st.status

        blocked: list[dict] = []
        for decomp in self._decompositions.values():
            for st in decomp.sub_tasks:
                # Skip already completed or skipped tasks
                if st.status in ("completed", "skipped"):
                    continue
                # Check if all deps are completed
                unmet = []
                for dep_id in st.dependencies:
                    dep_status = task_status_map.get(dep_id)
                    if dep_status != "completed":
                        unmet.append(dep_id)

                if unmet or st.status == "blocked":
                    blocked.append(
                        {
                            "feature_id": decomp.feature_id,
                            "feature_name": decomp.feature_name,
                            "task_id": st.task_id,
                            "task_name": st.name,
                            "agent": st.agent,
                            "status": st.status,
                            "unmet_dependencies": unmet,
                        }
                    )

        return blocked

    def get_completion_report(self) -> dict:
        """
        Get overall completion report.

        Returns:
            Dict with:
                total_features, total_sub_tasks,
                completed_sub_tasks, pending_sub_tasks,
                blocked_sub_tasks, in_progress_sub_tasks,
                skipped_sub_tasks, total_estimated_hours,
                completed_hours, completion_pct,
                feature_breakdown (list of dicts).
        """
        total_features = len(self._decompositions)
        total_sub_tasks = 0
        completed = 0
        pending = 0
        blocked = 0
        in_progress = 0
        skipped = 0
        total_hours = 0.0
        completed_hours = 0.0
        feature_breakdown: list[dict] = []

        for decomp in self._decompositions.values():
            f_total = len(decomp.sub_tasks)
            f_completed = 0
            f_hours = 0.0
            f_completed_hours = 0.0

            for st in decomp.sub_tasks:
                total_sub_tasks += 1
                f_total_actual = f_total
                total_hours += st.estimate_hours
                f_hours += st.estimate_hours

                if st.status == "completed":
                    completed += 1
                    f_completed += 1
                    completed_hours += st.estimate_hours
                    f_completed_hours += st.estimate_hours
                elif st.status == "pending":
                    pending += 1
                elif st.status == "blocked":
                    blocked += 1
                elif st.status == "in_progress":
                    in_progress += 1
                elif st.status == "skipped":
                    skipped += 1
                (f_total,)

            feat_pct = (
                round(
                    f_completed / max(f_total, 1) * 100,
                    1,
                )
                if f_total > 0
                else 0.0
            )
            feature_breakdown.append(
                {
                    "feature_id": decomp.feature_id,
                    "feature_name": decomp.feature_name,
                    "total_tasks": f_total,
                    "completed_tasks": f_completed,
                    "completion_pct": feat_pct,
                    "total_hours": round(f_hours, 2),
                    "completed_hours": round(
                        f_completed_hours,
                        2,
                    ),
                }
            )

        overall_pct = (
            round(
                completed / max(total_sub_tasks, 1) * 100,
                1,
            )
            if total_sub_tasks > 0
            else 0.0
        )

        return {
            "total_features": total_features,
            "total_sub_tasks": total_sub_tasks,
            "completed_sub_tasks": completed,
            "pending_sub_tasks": pending,
            "blocked_sub_tasks": blocked,
            "in_progress_sub_tasks": in_progress,
            "skipped_sub_tasks": skipped,
            "total_estimated_hours": round(
                total_hours,
                2,
            ),
            "completed_hours": round(completed_hours, 2),
            "completion_pct": overall_pct,
            "feature_breakdown": feature_breakdown,
        }

    # ── Utility Methods ──────────────────────────────────────────

    def get_feature_subtask_map(self) -> dict[str, list[str]]:
        """
        Get a mapping of feature_id -> [task_ids].

        Returns:
            Dict mapping feature IDs to their task ID lists.
        """
        result: dict[str, list[str]] = {}
        for decomp in self._decompositions.values():
            result[decomp.feature_id] = [st.task_id for st in decomp.sub_tasks]
        return result

    def get_task_feature_map(self) -> dict[str, str]:
        """
        Get a mapping of task_id -> feature_id.

        Returns:
            Dict mapping task IDs to their parent feature IDs.
        """
        result: dict[str, str] = {}
        for decomp in self._decompositions.values():
            for st in decomp.sub_tasks:
                result[st.task_id] = decomp.feature_id
        return result

    def delete_decomposition(
        self,
        feature_id: str,
    ) -> TaskDecomposition:
        """
        Delete a feature's decomposition.

        Args:
            feature_id: Feature identifier.

        Returns:
            The deleted TaskDecomposition.

        Raises:
            NotFoundError: If feature not found.
        """
        _validate_feature_id(feature_id)
        fid = feature_id.strip()

        decomp = self._decompositions.pop(fid, None)
        if decomp is None:
            raise NotFoundError(
                message=(f"Feature '{fid}' not found"),
            )
        return decomp
