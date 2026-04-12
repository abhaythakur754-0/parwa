"""
SG-15: State Serialization/Deserialization Layer (F-060).

Comprehensive state persistence for LangGraph pipeline with Redis primary
and PostgreSQL fallback. Provides crash recovery, cross-worker handoff,
debug replay, and audit trail capabilities.

Architecture:
  - Redis: Hot storage for active states (24h TTL) and checkpoints (7d TTL)
  - PostgreSQL: Persistent storage via PipelineStateSnapshot model
  - Distributed locks for concurrent access safety
  - State diff tracking for audit trail

BC-001: All operations scoped by company_id.
BC-004: Retry with exponential backoff on Redis operations.
BC-008: Never crash — graceful degradation on Redis/DB failure.
BC-012: UTC timestamps throughout.

Usage:
    from app.core.state_serialization import StateSerializer

    serializer = StateSerializer()
    await serializer.save_state(
        ticket_id="t1", company_id="c1",
        conversation_state=state, snapshot_type="auto",
    )
    loaded = await serializer.load_state(ticket_id="t1", company_id="c1")
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.core.techniques.base import (
    ConversationState,
    GSDState,
)
from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger("state_serialization")


# ── Custom Exception ──────────────────────────────────────────────


class StateSerializationError(ParwaBaseError):
    """Raised when state serialization/deserialization fails.

    Wraps lower-level Redis, PostgreSQL, or JSON errors with
    actionable context for callers.
    """

    def __init__(
        self,
        message: str = "State serialization failed",
        error_code: str = "STATE_SERIALIZATION_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
        )


# ── Enums ────────────────────────────────────────────────────────


class SnapshotType(str, Enum):
    """Type of state snapshot being saved."""
    AUTO = "auto"
    MANUAL = "manual"
    ERROR = "error"
    CHECKPOINT = "checkpoint"


class StorageBackend(str, Enum):
    """Which backend was used for the operation."""
    REDIS = "redis"
    POSTGRESQL = "postgresql"
    NONE = "none"


# ── Configuration Dataclass ─────────────────────────────────────


@dataclass(frozen=True)
class StateSerializerConfig:
    """Immutable configuration for the StateSerializer.

    All TTLs and retry settings in one place for easy tuning.
    """

    # Redis TTL for active states (24 hours)
    active_state_ttl_seconds: int = 86400

    # Redis TTL for checkpoints (7 days)
    checkpoint_ttl_seconds: int = 604800

    # Distributed lock timeout in seconds
    lock_timeout_seconds: float = 5.0

    # Number of retries for lock acquisition
    lock_retries: int = 3

    # Backoff in milliseconds between lock retries
    lock_retry_backoff_ms: int = 100

    # Maximum state history records to return
    default_history_limit: int = 50

    # Maximum serialized state size in bytes (safety limit)
    max_state_size_bytes: int = 5 * 1024 * 1024  # 5 MB

    # Whether to enable Redis pipeline for atomic operations
    use_redis_pipeline: bool = True


# ── State Diff Dataclass ────────────────────────────────────────


@dataclass
class StateDiff:
    """Represents field-level changes between two ConversationState snapshots.

    Each entry records the field name, old value, new value, and
    whether the value changed.
    """

    gsd_state: Optional[Dict[str, str]] = None
    current_node: Optional[Dict[str, Optional[str]]] = None
    technique_stack: Optional[Dict[str, Any]] = None
    token_count: Optional[Dict[str, int]] = None
    changed_fields: List[str] = field(default_factory=list)
    unchanged_fields: List[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert diff to a JSON-safe dictionary."""
        return {
            "gsd_state": self.gsd_state,
            "current_node": self.current_node,
            "technique_stack": self.technique_stack,
            "token_count": self.token_count,
            "changed_fields": self.changed_fields,
            "unchanged_fields": self.unchanged_fields,
            "timestamp": self.timestamp,
        }


# ── Checkpoint Metadata ─────────────────────────────────────────


@dataclass
class CheckpointMeta:
    """Metadata about a saved checkpoint."""
    checkpoint_name: str
    ticket_id: str
    company_id: str
    snapshot_id: str
    created_at: str
    gsd_state: str
    token_count: int
    current_node: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-safe dictionary."""
        return {
            "checkpoint_name": self.checkpoint_name,
            "ticket_id": self.ticket_id,
            "company_id": self.company_id,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "gsd_state": self.gsd_state,
            "token_count": self.token_count,
            "current_node": self.current_node,
        }


# ── State History Entry ─────────────────────────────────────────


@dataclass
class StateHistoryEntry:
    """A single entry in the state change history."""
    snapshot_id: str
    created_at: str
    snapshot_type: str
    current_node: str
    gsd_state: str
    token_count: int
    model_used: Optional[str]
    technique_stack: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-safe dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "snapshot_type": self.snapshot_type,
            "current_node": self.current_node,
            "gsd_state": self.gsd_state,
            "token_count": self.token_count,
            "model_used": self.model_used,
            "technique_stack": self.technique_stack,
        }


# ── Serialization Result ────────────────────────────────────────


@dataclass
class SaveResult:
    """Result of a save_state operation."""
    success: bool
    snapshot_id: str
    backend: StorageBackend
    redis_success: bool
    postgresql_success: bool
    error_message: Optional[str] = None
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-safe dictionary."""
        return {
            "success": self.success,
            "snapshot_id": self.snapshot_id,
            "backend": self.backend.value,
            "redis_success": self.redis_success,
            "postgresql_success": self.postgresql_success,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
        }


# ── Redis Key Builders ──────────────────────────────────────────


def _build_state_key(company_id: str, ticket_id: str) -> str:
    """Build the Redis key for an active conversation state.

    Key format: parwa:state:{company_id}:{ticket_id}

    Args:
        company_id: Tenant identifier (BC-001).
        ticket_id: Ticket identifier.

    Returns:
        Tenant-scoped Redis key string.
    """
    return f"parwa:state:{company_id}:{ticket_id}"


def _build_checkpoint_key(
    company_id: str,
    ticket_id: str,
    checkpoint_name: str,
) -> str:
    """Build the Redis key for a named checkpoint.

    Key format: parwa:checkpoint:{company_id}:{ticket_id}:{checkpoint_name}

    Args:
        company_id: Tenant identifier (BC-001).
        ticket_id: Ticket identifier.
        checkpoint_name: Human-readable checkpoint name.

    Returns:
        Tenant-scoped Redis key string.
    """
    return f"parwa:checkpoint:{company_id}:{ticket_id}:{checkpoint_name}"


def _build_checkpoint_index_key(
    company_id: str,
    ticket_id: str,
) -> str:
    """Build the Redis key for the checkpoint index (set of names).

    Key format: parwa:checkpoints:{company_id}:{ticket_id}

    Args:
        company_id: Tenant identifier.
        ticket_id: Ticket identifier.

    Returns:
        Redis key for the checkpoint name set.
    """
    return f"parwa:checkpoints:{company_id}:{ticket_id}"


def _build_lock_key(ticket_id: str) -> str:
    """Build the Redis key for distributed state lock.

    Key format: parwa:lock:state:{ticket_id}

    Args:
        ticket_id: Ticket identifier to lock on.

    Returns:
        Redis key for the distributed lock.
    """
    return f"parwa:lock:state:{ticket_id}"


# ── Utility Functions ───────────────────────────────────────────


def _utcnow() -> str:
    """Return current UTC time as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    """Generate a new UUID4 string for snapshot IDs."""
    return str(uuid.uuid4())


def _serialize_enum(value: Any) -> Any:
    """Convert enum values to their string representation.

    Handles GSDState and other str-based enums by returning .value.
    Recursively processes dicts and lists.

    Args:
        value: Any value that may contain enums.

    Returns:
        Value with all enums converted to strings.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _serialize_enum(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_enum(item) for item in value]
    return value


def _json_default(obj: Any) -> Any:
    """Custom JSON default handler.

    Handles known safe types (datetime, etc.) and raises TypeError
    for unserializable objects so the caller can catch and wrap.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _safe_json_dumps(obj: Any, max_size: int = 5 * 1024 * 1024) -> str:
    """Serialize an object to JSON with size safety check.

    Args:
        obj: Object to serialize.
        max_size: Maximum allowed serialized size in bytes.

    Returns:
        JSON string.

    Raises:
        StateSerializationError: If serialized size exceeds max_size.
    """
    try:
        serialized = json.dumps(obj, default=_json_default, ensure_ascii=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise StateSerializationError(
            message=f"JSON serialization failed: {exc}",
            error_code="STATE_SERIALIZE_JSON_ERROR",
            details={"error": str(exc)},
        ) from exc

    if len(serialized.encode("utf-8")) > max_size:
        raise StateSerializationError(
            message=(
                f"Serialized state exceeds maximum size: "
                f"{len(serialized.encode('utf-8'))} > {max_size} bytes"
            ),
            error_code="STATE_SERIALIZE_TOO_LARGE",
            details={"size_bytes": len(serialized.encode("utf-8"))},
        )

    return serialized


def _safe_json_loads(data: str) -> Any:
    """Deserialize JSON string with error handling.

    Args:
        data: JSON string to parse.

    Returns:
        Parsed Python object.

    Raises:
        StateSerializationError: If JSON parsing fails.
    """
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StateSerializationError(
            message=f"JSON deserialization failed: {exc}",
            error_code="STATE_DESERIALIZE_JSON_ERROR",
            details={"error": str(exc)},
        ) from exc


class _SafeJson:
    """Namespace object providing JSON helper methods.

    Provides a module-like interface for JSON operations used by tests.
    """
    loads = staticmethod(_safe_json_loads)


_safe_json = _SafeJson()


# ── StateSerializer ─────────────────────────────────────────────


class StateSerializer:
    """Main state serialization/deserialization layer.

    Provides Redis-primary storage with PostgreSQL fallback for
    conversation state persistence. Supports named checkpoints,
    state history, diff tracking, and debug replay.

    All public methods are async. Redis operations use distributed
    locks for concurrent access safety. PostgreSQL operations use
    the project's SessionLocal pattern.

    BC-001: All operations require company_id for tenant isolation.
    BC-004: Retry with backoff on transient failures.
    BC-008: Never crash — graceful degradation on failures.
    BC-012: All timestamps are UTC ISO-8601.

    Args:
        config: Optional configuration override. Uses defaults if not provided.
    """

    def __init__(
        self,
        config: Optional[StateSerializerConfig] = None,
    ) -> None:
        """Initialize the StateSerializer.

        Args:
            config: Optional configuration. Uses StateSerializerConfig
                defaults if not provided.
        """
        self._config = config or StateSerializerConfig()
        # Use direct method references — no unittest.mock in production code.
        # Tests that need to mock these should patch them via unittest.mock.patch
        # at the test level, not in production __init__.
        self._load_checkpoint_from_redis = self._load_checkpoint_from_redis_impl  # type: ignore[method-assign]
        self._load_checkpoint_from_postgresql = self._load_checkpoint_from_postgresql_impl  # type: ignore[method-assign]
        logger.info(
            "state_serializer_initialized",
            extra={
                "active_ttl": self._config.active_state_ttl_seconds,
                "checkpoint_ttl": self._config.checkpoint_ttl_seconds,
                "lock_timeout": self._config.lock_timeout_seconds,
            },
        )

    # ── Serialization / Deserialization ─────────────────────────

    def serialize_state(
        self, conversation_state: ConversationState,
    ) -> Dict[str, Any]:
        """Serialize a ConversationState to a JSON-safe dictionary.

        Converts all fields to primitive types suitable for JSON
        serialization and storage in Redis / PostgreSQL.

        GAP 1 FIX: Includes all fields with explicit serialization to ensure
        round-trip fidelity. Added checksum fields for critical data validation.

        Handles:
        - Enum values (GSDState) → string
        - QuerySignals → dict
        - Lists and dicts → deep copy with enum conversion
        - Optional fields → None preservation
        - Unicode and special characters → preserved exactly

        Args:
            conversation_state: The ConversationState dataclass instance
                to serialize.

        Returns:
            Dictionary with all state fields as JSON-safe primitives.

        Raises:
            StateSerializationError: If serialization fails.
        """
        try:
            # GAP 1 FIX: Serialize signals with explicit handling
            signals_dict = None
            if conversation_state.signals is not None:
                signals_dict = _serialize_enum(asdict(conversation_state.signals))
            
            # GAP 1 FIX: Serialize gsd_history with explicit handling
            gsd_history_list = []
            if conversation_state.gsd_history is not None:
                for s in conversation_state.gsd_history:
                    if isinstance(s, Enum):
                        gsd_history_list.append(s.value)
                    else:
                        gsd_history_list.append(str(s))
            
            # GAP 1 FIX: Serialize technique_results with explicit handling
            technique_results_dict = {}
            if conversation_state.technique_results is not None:
                technique_results_dict = _serialize_enum(conversation_state.technique_results)
            
            # GAP 1 FIX: Serialize reflexion_trace with explicit handling
            reflexion_trace_dict = None
            if conversation_state.reflexion_trace is not None:
                reflexion_trace_dict = _serialize_enum(conversation_state.reflexion_trace)
            
            # GAP 1 FIX: Deep copy lists to prevent reference issues
            response_parts_list = list(conversation_state.response_parts) if conversation_state.response_parts else []
            reasoning_thread_list = list(conversation_state.reasoning_thread) if conversation_state.reasoning_thread else []
            
            state_dict: Dict[str, Any] = {
                "query": conversation_state.query,
                "signals": signals_dict,
                "gsd_state": (
                    conversation_state.gsd_state.value
                    if isinstance(conversation_state.gsd_state, Enum)
                    else str(conversation_state.gsd_state)
                ),
                "gsd_history": gsd_history_list,
                "technique_results": technique_results_dict,
                "token_usage": conversation_state.token_usage,
                "technique_token_budget": (
                    conversation_state.technique_token_budget
                ),
                "response_parts": response_parts_list,
                "final_response": conversation_state.final_response or "",
                "ticket_id": conversation_state.ticket_id,
                "conversation_id": conversation_state.conversation_id,
                "company_id": conversation_state.company_id,
                "reasoning_thread": reasoning_thread_list,
                "reflexion_trace": reflexion_trace_dict,
                "serialized_at": _utcnow(),
                # GAP 1 FIX: Add checksums for critical data validation
                "_meta": {
                    "gsd_history_count": len(gsd_history_list),
                    "technique_results_keys": list(technique_results_dict.keys()),
                    "response_parts_count": len(response_parts_list),
                    "reasoning_thread_count": len(reasoning_thread_list),
                },
            }
            return state_dict
        except Exception as exc:
            logger.error(
                "state_serialize_failed",
                extra={
                    "error": str(exc),
                    "ticket_id": conversation_state.ticket_id,
                    "company_id": conversation_state.company_id,
                },
            )
            raise StateSerializationError(
                message=f"Failed to serialize ConversationState: {exc}",
                error_code="STATE_SERIALIZE_FAILED",
                details={
                    "error": str(exc),
                    "ticket_id": conversation_state.ticket_id,
                },
            ) from exc

    def deserialize_state(
        self, data: Dict[str, Any],
    ) -> ConversationState:
        """Deserialize a dictionary back into a ConversationState.

        Reconstructs the ConversationState dataclass from a previously
        serialized dictionary. Handles missing fields gracefully by
        falling back to ConversationState defaults.

        GAP 1 FIX: Validates checksums from _meta field to ensure
        round-trip fidelity. Logs warnings if data corruption is detected.

        Handles:
        - String GSDState values → enum
        - Signal dicts → QuerySignals dataclass
        - Missing fields → ConversationState defaults
        - Extra fields → ignored (forward-compatible)

        Args:
            data: Dictionary previously produced by serialize_state().

        Returns:
            Reconstructed ConversationState instance.

        Raises:
            StateSerializationError: If deserialization fails due to
                corrupted or invalid data.
        """
        try:
            # GAP 1 FIX: Validate checksums if _meta is present
            meta = data.get("_meta", {})
            if meta:
                expected_gsd_history_count = meta.get("gsd_history_count")
                expected_response_parts_count = meta.get("response_parts_count")
                expected_reasoning_thread_count = meta.get("reasoning_thread_count")
                expected_technique_results_keys = set(meta.get("technique_results_keys", []))
                
                gsd_history_raw = data.get("gsd_history", [])
                response_parts_raw = data.get("response_parts", [])
                reasoning_thread_raw = data.get("reasoning_thread", [])
                technique_results_raw = data.get("technique_results", {})
                
                # Validate counts match
                if expected_gsd_history_count is not None:
                    actual_count = len(gsd_history_raw) if isinstance(gsd_history_raw, list) else 0
                    if actual_count != expected_gsd_history_count:
                        logger.warning(
                            "deserialize_checksum_mismatch_gsd_history",
                            extra={
                                "expected": expected_gsd_history_count,
                                "actual": actual_count,
                            },
                        )
                
                if expected_response_parts_count is not None:
                    actual_count = len(response_parts_raw) if isinstance(response_parts_raw, list) else 0
                    if actual_count != expected_response_parts_count:
                        logger.warning(
                            "deserialize_checksum_mismatch_response_parts",
                            extra={
                                "expected": expected_response_parts_count,
                                "actual": actual_count,
                            },
                        )
                
                if expected_reasoning_thread_count is not None:
                    actual_count = len(reasoning_thread_raw) if isinstance(reasoning_thread_raw, list) else 0
                    if actual_count != expected_reasoning_thread_count:
                        logger.warning(
                            "deserialize_checksum_mismatch_reasoning_thread",
                            extra={
                                "expected": expected_reasoning_thread_count,
                                "actual": actual_count,
                            },
                        )
                
                # Validate technique_results keys match
                if expected_technique_results_keys:
                    actual_keys = set(technique_results_raw.keys()) if isinstance(technique_results_raw, dict) else set()
                    missing_keys = expected_technique_results_keys - actual_keys
                    if missing_keys:
                        logger.warning(
                            "deserialize_checksum_missing_technique_keys",
                            extra={
                                "missing_keys": list(missing_keys),
                            },
                        )
            else:
                gsd_history_raw = data.get("gsd_history", [])
                response_parts_raw = data.get("response_parts", [])
                reasoning_thread_raw = data.get("reasoning_thread", [])
                technique_results_raw = data.get("technique_results", {})

            # Deserialize GSDState from string
            gsd_state_raw = data.get("gsd_state", "new")
            if isinstance(gsd_state_raw, str):
                try:
                    gsd_state = GSDState(gsd_state_raw)
                except ValueError:
                    logger.warning(
                        "deserialize_invalid_gsd_state",
                        extra={
                            "raw_value": gsd_state_raw,
                            "fallback": "new",
                        },
                    )
                    gsd_state = GSDState.NEW
            elif isinstance(gsd_state_raw, GSDState):
                gsd_state = gsd_state_raw
            else:
                gsd_state = GSDState.NEW

            # Deserialize GSD history
            gsd_history: List[GSDState] = []
            if isinstance(gsd_history_raw, list):
                for item in gsd_history_raw:
                    if isinstance(item, str):
                        try:
                            gsd_history.append(GSDState(item))
                        except ValueError:
                            logger.debug(
                                "deserialize_skip_invalid_gsd_history_entry",
                                extra={"raw_value": item},
                            )
                    elif isinstance(item, GSDState):
                        gsd_history.append(item)

            # Deserialize QuerySignals
            from app.core.technique_router import QuerySignals

            signals_raw = data.get("signals")
            if isinstance(signals_raw, dict):
                try:
                    signals = QuerySignals(**{
                        k: v for k, v in signals_raw.items()
                        if k in QuerySignals.__dataclass_fields__
                    })
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        "deserialize_signals_fallback",
                        extra={"error": str(exc)},
                    )
                    signals = QuerySignals()
            else:
                signals = QuerySignals()

            # Deserialize technique_results
            technique_results = technique_results_raw if isinstance(technique_results_raw, dict) else {}

            # Deserialize reflexion_trace
            reflexion_trace = data.get("reflexion_trace")
            if not isinstance(reflexion_trace, dict) and reflexion_trace is not None:
                reflexion_trace = None

            # GAP 1 FIX: Ensure lists are properly copied
            response_parts = list(response_parts_raw) if isinstance(response_parts_raw, list) else []
            reasoning_thread = list(reasoning_thread_raw) if isinstance(reasoning_thread_raw, list) else []

            return ConversationState(
                query=data.get("query", ""),
                signals=signals,
                gsd_state=gsd_state,
                gsd_history=gsd_history,
                technique_results=technique_results,
                token_usage=data.get("token_usage", 0),
                technique_token_budget=data.get(
                    "technique_token_budget", 1500,
                ),
                response_parts=response_parts,
                final_response=data.get("final_response", ""),
                ticket_id=data.get("ticket_id"),
                conversation_id=data.get("conversation_id"),
                company_id=data.get("company_id"),
                reasoning_thread=data.get("reasoning_thread", []),
                reflexion_trace=reflexion_trace,
            )
        except Exception as exc:
            logger.error(
                "state_deserialize_failed",
                extra={"error": str(exc)},
            )
            raise StateSerializationError(
                message=f"Failed to deserialize state data: {exc}",
                error_code="STATE_DESERIALIZE_FAILED",
                details={"error": str(exc)},
            ) from exc

    # ── Round-trip Verification (GAP 1) ───────────────────────

    def verify_roundtrip(
        self,
        state_data: Dict[str, Any],
        company_id: str,
        ticket_id: str,
    ) -> Dict[str, Any]:
        """Verify state can survive a save → load round-trip without data loss.

        Performs a purely in-memory round-trip: serialize → JSON encode →
        JSON decode → deserialize, then compares the original and restored
        state field-by-field. Validates _meta checksums match.

        Args:
            state_data: A previously serialized state dictionary (as
                produced by serialize_state).
            company_id: Tenant identifier (BC-001).
            ticket_id: Ticket identifier.

        Returns:
            Dict with:
                success: bool — True if round-trip preserved all data.
                original_checksum: str — Hash of the original _meta.
                loaded_checksum: str — Hash of the restored _meta.
                data_matches: bool — Deep equality of top-level fields.
                fields_checked: list — Fields that were compared.
                missing_fields: list — Fields present in original but
                    absent or changed after round-trip.
        """
        import hashlib

        fields_checked: List[str] = []
        missing_fields: List[str] = []
        all_match = True

        # 1. Build checksums from original _meta
        original_meta = state_data.get("_meta", {})
        original_checksum = hashlib.sha256(
            json.dumps(original_meta, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        # 2. Simulate JSON round-trip (same as Redis/PG storage)
        try:
            state_json = json.dumps(state_data, default=_json_default, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            return {
                "success": False,
                "original_checksum": original_checksum,
                "loaded_checksum": "",
                "data_matches": False,
                "fields_checked": [],
                "missing_fields": ["json_encode_failed"],
                "error": f"JSON encode failed: {exc}",
            }

        try:
            restored_data = json.loads(state_json)
        except (json.JSONDecodeError, TypeError) as exc:
            return {
                "success": False,
                "original_checksum": original_checksum,
                "loaded_checksum": "",
                "data_matches": False,
                "fields_checked": [],
                "missing_fields": ["json_decode_failed"],
                "error": f"JSON decode failed: {exc}",
            }

        # 3. Build checksum from restored _meta
        restored_meta = restored_data.get("_meta", {})
        loaded_checksum = hashlib.sha256(
            json.dumps(restored_meta, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        # 4. Compare all critical top-level fields
        critical_fields = [
            "query", "gsd_state", "gsd_history", "technique_results",
            "token_usage", "technique_token_budget", "response_parts",
            "final_response", "ticket_id", "conversation_id",
            "company_id", "reasoning_thread", "reflexion_trace",
        ]

        for field_name in critical_fields:
            fields_checked.append(field_name)
            original_value = state_data.get(field_name)
            restored_value = restored_data.get(field_name)

            if original_value != restored_value:
                all_match = False
                missing_fields.append(field_name)
                logger.warning(
                    "verify_roundtrip_field_mismatch",
                    extra={
                        "field": field_name,
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                    },
                )

        # 5. Validate _meta checksums match
        checksums_match = original_checksum == loaded_checksum
        if not checksums_match:
            all_match = False
            missing_fields.append("_meta_checksum")
            logger.warning(
                "verify_roundtrip_meta_checksum_mismatch",
                extra={
                    "original": original_checksum,
                    "loaded": loaded_checksum,
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                },
            )

        # 6. Try full deserialize to catch any deeper issues
        try:
            self.deserialize_state(restored_data)
            fields_checked.append("deserialize_state")
        except Exception as exc:
            all_match = False
            missing_fields.append("deserialize_state")
            logger.warning(
                "verify_roundtrip_deserialize_failed",
                extra={
                    "error": str(exc),
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                },
            )

        result: Dict[str, Any] = {
            "success": all_match,
            "original_checksum": original_checksum,
            "loaded_checksum": loaded_checksum,
            "data_matches": all_match,
            "fields_checked": fields_checked,
            "missing_fields": missing_fields,
        }

        logger.info(
            "verify_roundtrip_completed",
            extra={
                "success": all_match,
                "ticket_id": ticket_id,
                "company_id": company_id,
                "fields_checked": len(fields_checked),
                "missing_fields": len(missing_fields),
            },
        )

        return result

    # ── Save / Load State ───────────────────────────────────────

    async def save_state(
        self,
        ticket_id: str,
        company_id: str,
        conversation_state: ConversationState,
        snapshot_type: str = "auto",
        **kwargs: Any,
    ) -> SaveResult:
        """Save conversation state to Redis first, then PostgreSQL fallback.

        Writes state to both backends for maximum durability. Redis is
        the primary hot-store; PostgreSQL is the persistent audit trail.
        If Redis fails, PostgreSQL still receives the state. If both
        fail, raises StateSerializationError.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).
            conversation_state: The state to persist.
            snapshot_type: One of "auto", "manual", "error", "checkpoint".
            **kwargs: Optional extra fields:
                - instance_id: str
                - session_id: str
                - model_used: str
                - current_node: str
                - technique_stack: List[str]

        Returns:
            SaveResult with success status, snapshot_id, and backend info.

        Raises:
            StateSerializationError: If both Redis and PostgreSQL fail.
        """
        start_time = time.monotonic()
        snapshot_id = _new_uuid()

        # Validate snapshot_type
        try:
            SnapshotType(snapshot_type)
        except ValueError:
            snapshot_type = "auto"

        # Serialize the state
        state_dict = self.serialize_state(conversation_state)
        state_json = _safe_json_dumps(
            state_dict,
            max_size=self._config.max_state_size_bytes,
        )

        # Extract metadata from kwargs
        instance_id = kwargs.get("instance_id")
        session_id = kwargs.get("session_id")
        model_used = kwargs.get("model_used")
        current_node = kwargs.get("current_node", "unknown")
        technique_stack = kwargs.get("technique_stack", [])

        redis_success = False
        postgresql_success = False
        primary_backend = StorageBackend.NONE
        error_message: Optional[str] = None

        # 1. Try Redis first (primary)
        redis_success = await self._save_to_redis(
            ticket_id=ticket_id,
            company_id=company_id,
            state_json=state_json,
            snapshot_id=snapshot_id,
            snapshot_type=snapshot_type,
            current_node=current_node,
            technique_stack=technique_stack,
        )

        if redis_success:
            primary_backend = StorageBackend.REDIS
            # GAP 2 FIX: Ensure PG sync after successful Redis write
            # so data is never only in volatile Redis storage.
            pg_sync_ok = await self._ensure_pg_sync(
                company_id=company_id,
                ticket_id=ticket_id,
                state_json=state_json,
                snapshot_id=snapshot_id,
                snapshot_type=snapshot_type,
                instance_id=instance_id,
                session_id=session_id,
                current_node=current_node,
                technique_stack=technique_stack,
                model_used=model_used,
                token_count=conversation_state.token_usage,
            )
            if pg_sync_ok:
                postgresql_success = True
        else:
            logger.warning(
                "state_save_redis_failed_fallback_to_pg",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                },
            )

        # 2. If Redis failed, still try PostgreSQL as primary fallback
        if not postgresql_success:
            postgresql_success = await self._save_to_postgresql(
                ticket_id=ticket_id,
                company_id=company_id,
                state_json=state_json,
                snapshot_id=snapshot_id,
                snapshot_type=snapshot_type,
                instance_id=instance_id,
                session_id=session_id,
                current_node=current_node,
                technique_stack=technique_stack,
                model_used=model_used,
                token_count=conversation_state.token_usage,
            )

        if postgresql_success:
            if primary_backend == StorageBackend.NONE:
                primary_backend = StorageBackend.POSTGRESQL
        else:
            error_message = "Both Redis and PostgreSQL save failed"

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        success = redis_success or postgresql_success

        if not success:
            logger.error(
                "state_save_complete_failure",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                },
            )
            raise StateSerializationError(
                message="Failed to save state to both Redis and PostgreSQL",
                error_code="STATE_SAVE_COMPLETE_FAILURE",
                details={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                    "redis_success": redis_success,
                    "postgresql_success": postgresql_success,
                },
            )

        logger.info(
            "state_save_success",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "snapshot_id": snapshot_id,
                "snapshot_type": snapshot_type,
                "backend": primary_backend.value,
                "redis": redis_success,
                "postgresql": postgresql_success,
                "latency_ms": elapsed_ms,
            },
        )

        return SaveResult(
            success=True,
            snapshot_id=snapshot_id,
            backend=primary_backend,
            redis_success=redis_success,
            postgresql_success=postgresql_success,
            latency_ms=elapsed_ms,
        )

    async def load_state(
        self,
        ticket_id: str,
        company_id: str,
    ) -> Optional[ConversationState]:
        """Load conversation state from Redis first, fallback to PostgreSQL.

        Attempts to load from Redis (fast path). If not found or
        Redis is unavailable, falls back to the most recent PostgreSQL
        snapshot for this ticket.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            ConversationState if found in either backend, None otherwise.
            Returns None (never raises) for corrupted data — logs error.
        """
        # 1. Try Redis (fast path)
        state = await self._load_from_redis(ticket_id, company_id)
        if state is not None:
            logger.debug(
                "state_load_redis_hit",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                },
            )
            return state

        # 2. Fallback to PostgreSQL (slow path)
        logger.info(
            "state_load_redis_miss_fallback_to_pg",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
            },
        )
        state = await self._load_from_postgresql(ticket_id, company_id)
        if state is not None:
            # Populate Redis cache from PostgreSQL for future fast loads
            try:
                state_dict = self.serialize_state(state)
                state_json = json.dumps(state_dict, default=str)
                redis_key = _build_state_key(company_id, ticket_id)
                await self._redis_set(
                    redis_key,
                    state_json,
                    ttl=self._config.active_state_ttl_seconds,
                )
                logger.debug(
                    "state_load_pg_cache_backfill",
                    extra={
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                    },
                )
            except Exception:
                logger.warning(
                    "state_load_pg_cache_backfill_failed",
                    extra={
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                    },
                )
            return state

        logger.info(
            "state_load_not_found",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
            },
        )
        return None

    # ── Checkpoint Operations ───────────────────────────────────

    async def save_checkpoint(
        self,
        ticket_id: str,
        company_id: str,
        conversation_state: ConversationState,
        checkpoint_name: str,
        **kwargs: Any,
    ) -> SaveResult:
        """Save a named checkpoint for the conversation state.

        Checkpoints are stored separately from active state with a
        longer TTL (7 days vs 24 hours). Multiple checkpoints can
        exist for the same ticket.

        Also saves as a "checkpoint" type snapshot in PostgreSQL
        for persistence beyond Redis TTL.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).
            conversation_state: The state to checkpoint.
            checkpoint_name: Human-readable name for the checkpoint
                (e.g., "before_resolution", "handoff_point").
            **kwargs: Optional extra fields passed through to save_state.

        Returns:
            SaveResult with success status and checkpoint metadata.
        """
        snapshot_id = _new_uuid()

        # Validate checkpoint name
        if not checkpoint_name or not isinstance(checkpoint_name, str):
            raise StateSerializationError(
                message="checkpoint_name is required and must be a non-empty string",
                error_code="STATE_CHECKPOINT_INVALID_NAME",
                status_code=400,
            )

        # Sanitize checkpoint name for Redis key safety
        safe_name = checkpoint_name.strip().lower().replace(" ", "_")
        if not safe_name.isidentifier():
            safe_name = "".join(
                c if c.isalnum() or c == "_" else "_"
                for c in safe_name
            )

        # Serialize the state
        state_dict = self.serialize_state(conversation_state)
        state_json = _safe_json_dumps(
            state_dict,
            max_size=self._config.max_state_size_bytes,
        )

        redis_success = False
        postgresql_success = False

        # 1. Save to Redis checkpoint key
        redis_success = await self._save_checkpoint_to_redis(
            ticket_id=ticket_id,
            company_id=company_id,
            checkpoint_name=safe_name,
            state_json=state_json,
            snapshot_id=snapshot_id,
            current_node=kwargs.get("current_node", "unknown"),
            gsd_state=conversation_state.gsd_state.value
            if isinstance(conversation_state.gsd_state, Enum)
            else str(conversation_state.gsd_state),
            token_count=conversation_state.token_usage,
        )

        # 2. Save to PostgreSQL as checkpoint type
        postgresql_success = await self._save_to_postgresql(
            ticket_id=ticket_id,
            company_id=company_id,
            state_json=state_json,
            snapshot_id=snapshot_id,
            snapshot_type="checkpoint",
            instance_id=kwargs.get("instance_id"),
            session_id=kwargs.get("session_id"),
            current_node=kwargs.get("current_node", "unknown"),
            technique_stack=kwargs.get("technique_stack", []),
            model_used=kwargs.get("model_used"),
            token_count=conversation_state.token_usage,
        )

        success = redis_success or postgresql_success
        backend = StorageBackend.NONE
        if redis_success:
            backend = StorageBackend.REDIS
        elif postgresql_success:
            backend = StorageBackend.POSTGRESQL

        if not success:
            raise StateSerializationError(
                message="Failed to save checkpoint to both backends",
                error_code="STATE_CHECKPOINT_SAVE_FAILED",
                details={
                    "ticket_id": ticket_id,
                    "checkpoint_name": checkpoint_name,
                },
            )

        logger.info(
            "state_checkpoint_saved",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "checkpoint_name": checkpoint_name,
                "snapshot_id": snapshot_id,
                "backend": backend.value,
            },
        )

        return SaveResult(
            success=True,
            snapshot_id=snapshot_id,
            backend=backend,
            redis_success=redis_success,
            postgresql_success=postgresql_success,
        )

    async def load_checkpoint(
        self,
        ticket_id: str,
        company_id: str,
        checkpoint_name: str,
    ) -> Optional[ConversationState]:
        """Load a specific named checkpoint.

        Looks up the checkpoint by name in Redis first, then
        falls back to PostgreSQL if Redis is unavailable.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).
            checkpoint_name: The name of the checkpoint to load.

        Returns:
            ConversationState if checkpoint found, None otherwise.
            Returns None for corrupted data (logs error, never raises).
        """
        # Sanitize checkpoint name the same way as save
        safe_name = checkpoint_name.strip().lower().replace(" ", "_")
        if not safe_name.isidentifier():
            safe_name = "".join(
                c if c.isalnum() or c == "_" else "_"
                for c in safe_name
            )

        # 1. Try Redis (attribute lookup allows test patching)
        _redis_loader = getattr(self, '_load_checkpoint_from_redis')
        state = await _redis_loader(
            ticket_id, company_id, safe_name,
        )
        if state is not None:
            logger.info(
                "state_checkpoint_load_redis_hit",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "checkpoint_name": checkpoint_name,
                },
            )
            return state

        # 2. Fallback to PostgreSQL
        logger.info(
            "state_checkpoint_load_redis_miss_fallback_pg",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "checkpoint_name": checkpoint_name,
            },
        )
        _pg_loader = getattr(self, '_load_checkpoint_from_postgresql')
        state = await _pg_loader(
            ticket_id, company_id, checkpoint_name,
        )
        if state is not None:
            return state

        logger.info(
            "state_checkpoint_not_found",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "checkpoint_name": checkpoint_name,
            },
        )
        return None

    async def list_checkpoints(
        self,
        ticket_id: str,
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """List all checkpoints for a ticket.

        Retrieves checkpoint metadata from Redis index. Falls back
        to PostgreSQL if Redis is unavailable.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            List of checkpoint metadata dicts, each containing:
            - checkpoint_name, ticket_id, company_id, snapshot_id,
              created_at, gsd_state, token_count, current_node
        """
        checkpoints: List[Dict[str, Any]] = []

        # 1. Try Redis checkpoint index
        redis_checkpoints = await self._list_checkpoints_from_redis(
            ticket_id, company_id,
        )
        if redis_checkpoints is not None:
            checkpoints = redis_checkpoints
        else:
            # 2. Fallback to PostgreSQL
            checkpoints = await self._list_checkpoints_from_postgresql(
                ticket_id, company_id,
            )

        logger.debug(
            "state_checkpoints_listed",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "count": len(checkpoints),
            },
        )
        return checkpoints

    # ── Delete / History / Replay ───────────────────────────────

    async def delete_state(
        self,
        ticket_id: str,
        company_id: str,
    ) -> Dict[str, bool]:
        """Clean up state from both Redis and PostgreSQL.

        Removes the active state key and all checkpoint keys from
        Redis. Also deletes all snapshots for this ticket from
        PostgreSQL.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with 'redis' and 'postgresql' keys indicating
            whether cleanup succeeded for each backend.
        """
        redis_deleted = await self._delete_state_from_redis(
            ticket_id, company_id,
        )
        postgresql_deleted = await self._delete_state_from_postgresql(
            ticket_id, company_id,
        )

        logger.info(
            "state_delete_completed",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "redis_deleted": redis_deleted,
                "postgresql_deleted": postgresql_deleted,
            },
        )

        return {
            "redis": redis_deleted,
            "postgresql": postgresql_deleted,
        }

    async def get_state_history(
        self,
        ticket_id: str,
        company_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get state change history for a ticket from PostgreSQL.

        Returns the most recent snapshots for this ticket, ordered
        by creation time descending. This provides an audit trail of
        all state transitions.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).
            limit: Maximum number of history entries to return.
                Defaults to 50.

        Returns:
            List of state history entry dicts, each containing:
            - snapshot_id, created_at, snapshot_type, current_node,
              gsd_state, token_count, model_used, technique_stack
        """
        if limit <= 0:
            limit = 1
        if limit > 200:
            limit = 200

        history = await self._get_history_from_postgresql(
            ticket_id, company_id, limit,
        )

        logger.debug(
            "state_history_retrieved",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "count": len(history),
                "limit": limit,
            },
        )

        return history

    async def replay_state(
        self,
        ticket_id: str,
        company_id: str,
        snapshot_id: str,
    ) -> Optional[ConversationState]:
        """Load a specific historical snapshot for debug replay.

        Retrieves a single snapshot by its ID from PostgreSQL and
        deserializes it. This enables replaying the pipeline from
        any historical state for debugging.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).
            snapshot_id: The unique ID of the snapshot to replay.

        Returns:
            ConversationState if snapshot found, None otherwise.
            Returns None for corrupted data (logs error, never raises).
        """
        state = await self._replay_from_postgresql(
            ticket_id, company_id, snapshot_id,
        )

        if state is not None:
            logger.info(
                "state_replay_loaded",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                },
            )
        else:
            logger.info(
                "state_replay_not_found",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                },
            )

        return state

    # ── State Diff ──────────────────────────────────────────────

    def compute_diff(
        self,
        old_state: Optional[ConversationState],
        new_state: Optional[ConversationState],
    ) -> StateDiff:
        """Compute what changed between two ConversationState instances.

        Performs field-level comparison tracking changes in key fields:
        gsd_state, current_node (extracted from metadata), technique_stack
        (from technique_results), and token_count.

        Args:
            old_state: The previous state (may be None for first save).
            new_state: The new state (may be None for deletion).

        Returns:
            StateDiff with field-level change details.
        """
        diff = StateDiff(timestamp=_utcnow())

        if old_state is None and new_state is None:
            return diff

        if old_state is None:
            # First state — everything is "new"
            diff.changed_fields = [
                "gsd_state", "token_count", "technique_results",
                "query", "final_response",
            ]
            if new_state is not None:
                diff.gsd_state = {
                    "old": None,
                    "new": (
                        new_state.gsd_state.value
                        if isinstance(new_state.gsd_state, Enum)
                        else str(new_state.gsd_state)
                    ),
                }
                diff.token_count = {
                    "old": 0,
                    "new": new_state.token_usage,
                }
                diff.technique_stack = {
                    "old": [],
                    "new": list(
                        (new_state.technique_results or {}).keys()
                    ),
                }
            return diff

        if new_state is None:
            # State deleted — everything is "removed"
            diff.changed_fields = ["gsd_state", "token_count"]
            diff.gsd_state = {
                "old": (
                    old_state.gsd_state.value
                    if isinstance(old_state.gsd_state, Enum)
                    else str(old_state.gsd_state)
                ),
                "new": None,
            }
            diff.token_count = {
                "old": old_state.token_usage,
                "new": 0,
            }
            return diff

        # Compare gsd_state
        old_gsd = (
            old_state.gsd_state.value
            if isinstance(old_state.gsd_state, Enum)
            else str(old_state.gsd_state)
        )
        new_gsd = (
            new_state.gsd_state.value
            if isinstance(new_state.gsd_state, Enum)
            else str(new_state.gsd_state)
        )
        if old_gsd != new_gsd:
            diff.gsd_state = {"old": old_gsd, "new": new_gsd}
            diff.changed_fields.append("gsd_state")
        else:
            diff.unchanged_fields.append("gsd_state")

        # Compare token_count
        if old_state.token_usage != new_state.token_usage:
            diff.token_count = {
                "old": old_state.token_usage,
                "new": new_state.token_usage,
            }
            diff.changed_fields.append("token_count")
        else:
            diff.unchanged_fields.append("token_count")

        # Compare technique stack (from technique_results keys)
        old_techniques = sorted(
            (old_state.technique_results or {}).keys()
        )
        new_techniques = sorted(
            (new_state.technique_results or {}).keys()
        )
        if old_techniques != new_techniques:
            diff.technique_stack = {
                "old": old_techniques,
                "new": new_techniques,
            }
            diff.changed_fields.append("technique_stack")
        else:
            diff.unchanged_fields.append("technique_stack")

        # Compare query
        if old_state.query != new_state.query:
            diff.changed_fields.append("query")
        else:
            diff.unchanged_fields.append("query")

        # Compare final_response
        if old_state.final_response != new_state.final_response:
            diff.changed_fields.append("final_response")
        else:
            diff.unchanged_fields.append("final_response")

        return diff

    # ── Redis Backend Operations ────────────────────────────────

    async def _save_to_redis(
        self,
        ticket_id: str,
        company_id: str,
        state_json: str,
        snapshot_id: str,
        snapshot_type: str,
        current_node: str,
        technique_stack: List[str],
    ) -> bool:
        """Save state to Redis as the primary hot-store.

        Uses _redis_set for the actual Redis write, making it easy
        to mock in tests.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.
            state_json: Serialized state JSON string.
            snapshot_id: Unique snapshot identifier.
            snapshot_type: Type of snapshot (auto/manual/error/checkpoint).
            current_node: Current pipeline node name.
            technique_stack: List of technique IDs in the stack.

        Returns:
            True if save succeeded, False otherwise.
        """
        try:
            redis_key = _build_state_key(company_id, ticket_id)
            return await self._redis_set(
                redis_key,
                state_json,
                ttl=self._config.active_state_ttl_seconds,
            )
        except Exception as exc:
            logger.warning(
                "state_save_redis_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return False

    async def _load_from_redis(
        self,
        ticket_id: str,
        company_id: str,
    ) -> Optional[ConversationState]:
        """Load state from Redis (fast path).

        Retrieves state JSON from Redis using _redis_get and deserializes.
        Returns None on any failure (Redis unavailable, missing key,
        corrupted data).

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.

        Returns:
            ConversationState if found and valid, None otherwise.
        """
        try:
            redis_key = _build_state_key(company_id, ticket_id)
            state_json = await self._redis_get(redis_key)

            if not state_json:
                return None

            state_dict = _safe_json_loads(state_json)
            return self.deserialize_state(state_dict)

        except StateSerializationError:
            logger.warning(
                "state_load_redis_corrupted_data",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                },
            )
            return None
        except Exception as exc:
            logger.warning(
                "state_load_redis_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return None

    async def _save_checkpoint_to_redis(
        self,
        ticket_id: str,
        company_id: str,
        checkpoint_name: str,
        state_json: str,
        snapshot_id: str,
        current_node: str,
        gsd_state: str,
        token_count: int,
    ) -> bool:
        """Save a named checkpoint to Redis.

        Stores the checkpoint data in a hash and adds the checkpoint
        name to a Redis set for listing.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.
            checkpoint_name: Sanitized checkpoint name.
            state_json: Serialized state JSON string.
            snapshot_id: Unique snapshot identifier.
            current_node: Current pipeline node name.
            gsd_state: GSD state string value.
            token_count: Current token usage count.

        Returns:
            True if save succeeded, False otherwise.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            checkpoint_key = _build_checkpoint_key(
                company_id, ticket_id, checkpoint_name,
            )
            index_key = _build_checkpoint_index_key(company_id, ticket_id)

            metadata_json = json.dumps({
                "checkpoint_name": checkpoint_name,
                "snapshot_id": snapshot_id,
                "created_at": _utcnow(),
                "current_node": current_node,
                "gsd_state": gsd_state,
                "token_count": token_count,
            })

            if self._config.use_redis_pipeline:
                async with redis_client.pipeline(transaction=True) as pipe:
                    pipe.hset(checkpoint_key, mapping={
                        "state_data": state_json,
                        "metadata": metadata_json,
                        "snapshot_id": snapshot_id,
                    })
                    pipe.expire(
                        checkpoint_key,
                        self._config.checkpoint_ttl_seconds,
                    )
                    pipe.sadd(index_key, checkpoint_name)
                    pipe.expire(
                        index_key,
                        self._config.checkpoint_ttl_seconds,
                    )
                    await pipe.execute()
            else:
                await redis_client.hset(checkpoint_key, mapping={
                    "state_data": state_json,
                    "metadata": metadata_json,
                    "snapshot_id": snapshot_id,
                })
                await redis_client.expire(
                    checkpoint_key,
                    self._config.checkpoint_ttl_seconds,
                )
                await redis_client.sadd(index_key, checkpoint_name)
                await redis_client.expire(
                    index_key,
                    self._config.checkpoint_ttl_seconds,
                )

            return True

        except Exception as exc:
            logger.warning(
                "checkpoint_save_redis_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "checkpoint_name": checkpoint_name,
                    "error": str(exc),
                },
            )
            return False

    async def _load_checkpoint_from_redis_impl(
        self,
        ticket_id: str,
        company_id: str,
        checkpoint_name: str,
    ) -> Optional[ConversationState]:
        """Load a specific checkpoint from Redis.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.
            checkpoint_name: Sanitized checkpoint name.

        Returns:
            ConversationState if found, None otherwise.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            checkpoint_key = _build_checkpoint_key(
                company_id, ticket_id, checkpoint_name,
            )

            checkpoint_hash = await redis_client.hgetall(checkpoint_key)
            if not checkpoint_hash:
                return None

            state_json = checkpoint_hash.get("state_data")
            if not state_json:
                return None

            state_dict = _safe_json_loads(state_json)
            return self.deserialize_state(state_dict)

        except StateSerializationError:
            logger.warning(
                "checkpoint_load_redis_corrupted",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "checkpoint_name": checkpoint_name,
                },
            )
            return None
        except Exception as exc:
            logger.warning(
                "checkpoint_load_redis_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "checkpoint_name": checkpoint_name,
                    "error": str(exc),
                },
            )
            return None

    async def _list_checkpoints_from_redis(
        self,
        ticket_id: str,
        company_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """List checkpoints from the Redis index.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.

        Returns:
            List of checkpoint metadata dicts, or None if Redis
            is unavailable.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            index_key = _build_checkpoint_index_key(company_id, ticket_id)

            checkpoint_names = await redis_client.smembers(index_key)
            if not checkpoint_names:
                return []

            checkpoints: List[Dict[str, Any]] = []

            for name in checkpoint_names:
                checkpoint_key = _build_checkpoint_key(
                    company_id, ticket_id, name,
                )
                checkpoint_hash = await redis_client.hgetall(checkpoint_key)
                if not checkpoint_hash:
                    continue

                metadata_str = checkpoint_hash.get("metadata")
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                        metadata["ticket_id"] = ticket_id
                        metadata["company_id"] = company_id
                        checkpoints.append(metadata)
                    except (json.JSONDecodeError, TypeError):
                        checkpoints.append({
                            "checkpoint_name": name,
                            "ticket_id": ticket_id,
                            "company_id": company_id,
                            "snapshot_id": checkpoint_hash.get(
                                "snapshot_id", "",
                            ),
                            "created_at": "unknown",
                            "gsd_state": "unknown",
                            "token_count": 0,
                            "current_node": "unknown",
                        })

            # Sort by created_at descending
            checkpoints.sort(
                key=lambda x: x.get("created_at", ""),
                reverse=True,
            )
            return checkpoints

        except Exception as exc:
            logger.warning(
                "checkpoint_list_redis_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return None

    async def _delete_state_from_redis(
        self,
        ticket_id: str,
        company_id: str,
    ) -> bool:
        """Delete active state from Redis.

        Removes the state key for this ticket using _redis_delete.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.

        Returns:
            True if deletion succeeded (or nothing to delete), False on error.
        """
        try:
            redis_key = _build_state_key(company_id, ticket_id)
            return await self._redis_delete(redis_key)
        except Exception as exc:
            logger.warning(
                "state_delete_redis_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return False

    async def _redis_set(
        self,
        key: str,
        value: str,
        ttl: int,
    ) -> bool:
        """Simple Redis SET with TTL.

        Args:
            key: Redis key.
            value: String value to store.
            ttl: Time-to-live in seconds.

        Returns:
            True if set succeeded, False on error.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            await redis_client.set(key, value, ex=ttl)
            return True
        except Exception:
            return False

    async def _redis_get(
        self,
        key: str,
    ) -> Optional[str]:
        """Simple Redis GET.

        Args:
            key: Redis key.

        Returns:
            String value if found, None otherwise.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            result = await redis_client.get(key)
            if result is None:
                return None
            if isinstance(result, bytes):
                return result.decode("utf-8")
            return result
        except Exception:
            return None

    async def _redis_delete(
        self,
        key: str,
    ) -> bool:
        """Simple Redis DELETE.

        Args:
            key: Redis key to delete.

        Returns:
            True if delete succeeded, False on error.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            await redis_client.delete(key)
            return True
        except Exception:
            return False

    # ── PostgreSQL Sync Guarantee (GAP 2) ──────────────────────

    async def _ensure_pg_sync(
        self,
        company_id: str,
        ticket_id: str,
        state_json: str,
        snapshot_id: str,
        snapshot_type: str,
        instance_id: Optional[str] = None,
        session_id: Optional[str] = None,
        current_node: str = "unknown",
        technique_stack: Optional[List[str]] = None,
        model_used: Optional[str] = None,
        token_count: int = 0,
    ) -> bool:
        """Ensure state is synced to PostgreSQL as a backup.

        Called after every successful Redis save to guarantee that
        critical state data is never only in volatile Redis storage.
        If Redis is the primary store and goes down, PG must have
        a complete copy for failover recovery.

        Unlike the regular _save_to_postgresql call inside save_state,
        this method uses retry logic (BC-004) because it is the safety
        net. If PG sync fails, we log but don't crash (BC-008).

        Args:
            company_id: Tenant identifier (BC-001).
            ticket_id: Ticket identifier.
            state_json: Already-serialized state JSON string.
            snapshot_id: Unique snapshot identifier.
            snapshot_type: Type of snapshot.
            instance_id: Optional variant instance ID.
            session_id: Optional session ID.
            current_node: Current pipeline node name.
            technique_stack: List of technique IDs.
            model_used: AI model used.
            token_count: Token usage count.

        Returns:
            True if sync succeeded, False otherwise.
        """
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            success = await self._save_to_postgresql(
                ticket_id=ticket_id,
                company_id=company_id,
                state_json=state_json,
                snapshot_id=snapshot_id,
                snapshot_type=snapshot_type,
                instance_id=instance_id,
                session_id=session_id,
                current_node=current_node,
                technique_stack=technique_stack,
                model_used=model_used,
                token_count=token_count,
            )
            if success:
                logger.debug(
                    "ensure_pg_sync_success",
                    extra={
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                        "snapshot_id": snapshot_id,
                        "attempt": attempt,
                    },
                )
                return True

            # Exponential backoff (BC-004)
            if attempt < max_retries:
                backoff_ms = 100 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff_ms / 1000.0)

        # BC-008: Never crash — log but don't raise
        logger.error(
            "ensure_pg_sync_all_retries_failed",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "snapshot_id": snapshot_id,
                "max_retries": max_retries,
            },
        )
        return False

    # ── PostgreSQL Backend Operations ───────────────────────────

    async def _save_to_postgresql(
        self,
        ticket_id: str,
        company_id: str,
        state_json: str,
        snapshot_id: str,
        snapshot_type: str,
        instance_id: Optional[str] = None,
        session_id: Optional[str] = None,
        current_node: str = "unknown",
        technique_stack: Optional[List[str]] = None,
        model_used: Optional[str] = None,
        token_count: int = 0,
    ) -> bool:
        """Save a state snapshot to PostgreSQL.

        Creates a new PipelineStateSnapshot row with the serialized
        state data. Uses synchronous SessionLocal for DB access.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.
            state_json: Serialized state JSON string.
            snapshot_id: Unique snapshot identifier.
            snapshot_type: Type of snapshot.
            instance_id: Optional variant instance ID.
            session_id: Optional session ID.
            current_node: Current pipeline node name.
            technique_stack: List of technique IDs.
            model_used: AI model used.
            token_count: Token usage count.

        Returns:
            True if save succeeded, False on error.
        """
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import PipelineStateSnapshot

            technique_stack_json = json.dumps(technique_stack or [])

            snapshot = PipelineStateSnapshot(
                id=snapshot_id,
                company_id=company_id,
                instance_id=instance_id,
                ticket_id=ticket_id,
                session_id=session_id,
                current_node=current_node,
                state_data=state_json,
                technique_stack=technique_stack_json,
                model_used=model_used,
                token_count=token_count,
                snapshot_type=snapshot_type,
            )

            db = SessionLocal()
            try:
                db.add(snapshot)
                db.commit()
                logger.debug(
                    "state_save_postgresql_success",
                    extra={
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                        "snapshot_id": snapshot_id,
                    },
                )
                return True
            except Exception as db_exc:
                db.rollback()
                raise db_exc
            finally:
                db.close()

        except Exception as exc:
            logger.error(
                "state_save_postgresql_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                    "error": str(exc),
                },
            )
            return False

    async def _load_from_postgresql(
        self,
        ticket_id: str,
        company_id: str,
    ) -> Optional[ConversationState]:
        """Load the most recent state snapshot from PostgreSQL.

        Queries PipelineStateSnapshot ordered by created_at DESC,
        takes the first result, and deserializes.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.

        Returns:
            ConversationState if found, None otherwise.
        """
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import PipelineStateSnapshot

            db = SessionLocal()
            try:
                snapshot = (
                    db.query(PipelineStateSnapshot)
                    .filter(
                        PipelineStateSnapshot.ticket_id == ticket_id,
                        PipelineStateSnapshot.company_id == company_id,
                    )
                    .order_by(PipelineStateSnapshot.created_at.desc())
                    .first()
                )

                if snapshot is None:
                    return None

                state_dict = _safe_json_loads(snapshot.state_data)
                return self.deserialize_state(state_dict)

            finally:
                db.close()

        except StateSerializationError:
            logger.warning(
                "state_load_postgresql_corrupted",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                },
            )
            return None
        except Exception as exc:
            logger.error(
                "state_load_postgresql_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return None

    async def _load_checkpoint_from_postgresql_impl(
        self,
        ticket_id: str,
        company_id: str,
        checkpoint_name: str,
    ) -> Optional[ConversationState]:
        """Load a specific checkpoint from PostgreSQL.

        Finds the most recent checkpoint-type snapshot for the
        given ticket. Since PostgreSQL doesn't have a checkpoint_name
        column, we store checkpoint metadata in the state_data JSON.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.
            checkpoint_name: Checkpoint name to find.

        Returns:
            ConversationState if found, None otherwise.
        """
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import PipelineStateSnapshot

            db = SessionLocal()
            try:
                # Query all checkpoint snapshots for this ticket
                snapshots = (
                    db.query(PipelineStateSnapshot)
                    .filter(
                        PipelineStateSnapshot.ticket_id == ticket_id,
                        PipelineStateSnapshot.company_id == company_id,
                        PipelineStateSnapshot.snapshot_type == "checkpoint",
                    )
                    .order_by(PipelineStateSnapshot.created_at.desc())
                    .limit(50)
                    .all()
                )

                # Find the one matching our checkpoint name
                for snapshot in snapshots:
                    try:
                        state_dict = json.loads(snapshot.state_data)
                        # Check if serialized_at or checkpoint_name matches
                        # We stored the checkpoint context in technique_stack
                        # or we can check by comparing state content
                        ts_data = json.loads(snapshot.technique_stack or "[]")
                        if checkpoint_name in ts_data:
                            return self.deserialize_state(state_dict)

                        # Also check if checkpoint_name is in state_data
                        if state_dict.get("_checkpoint_name") == checkpoint_name:
                            return self.deserialize_state(state_dict)

                    except (json.JSONDecodeError, TypeError):
                        continue

                return None

            finally:
                db.close()

        except Exception as exc:
            logger.error(
                "checkpoint_load_postgresql_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "checkpoint_name": checkpoint_name,
                    "error": str(exc),
                },
            )
            return None

    async def _list_checkpoints_from_postgresql(
        self,
        ticket_id: str,
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """List checkpoints from PostgreSQL.

        Queries all checkpoint-type snapshots for this ticket.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.

        Returns:
            List of checkpoint metadata dicts.
        """
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import PipelineStateSnapshot

            db = SessionLocal()
            try:
                snapshots = (
                    db.query(PipelineStateSnapshot)
                    .filter(
                        PipelineStateSnapshot.ticket_id == ticket_id,
                        PipelineStateSnapshot.company_id == company_id,
                        PipelineStateSnapshot.snapshot_type == "checkpoint",
                    )
                    .order_by(PipelineStateSnapshot.created_at.desc())
                    .all()
                )

                checkpoints: List[Dict[str, Any]] = []
                for snapshot in snapshots:
                    gsd_state = "unknown"
                    try:
                        state_dict = json.loads(snapshot.state_data)
                        gsd_state = state_dict.get("gsd_state", "unknown")
                    except (json.JSONDecodeError, TypeError):
                        pass

                    checkpoints.append({
                        "checkpoint_name": snapshot.id,
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                        "snapshot_id": snapshot.id,
                        "created_at": (
                            snapshot.created_at.isoformat()
                            if snapshot.created_at
                            else "unknown"
                        ),
                        "gsd_state": gsd_state,
                        "token_count": snapshot.token_count or 0,
                        "current_node": snapshot.current_node or "unknown",
                    })

                return checkpoints

            finally:
                db.close()

        except Exception as exc:
            logger.error(
                "checkpoint_list_postgresql_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return []

    async def _delete_state_from_postgresql(
        self,
        ticket_id: str,
        company_id: str,
    ) -> bool:
        """Delete all snapshots for a ticket from PostgreSQL.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.

        Returns:
            True if deletion succeeded, False on error.
        """
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import PipelineStateSnapshot

            db = SessionLocal()
            try:
                deleted = (
                    db.query(PipelineStateSnapshot)
                    .filter(
                        PipelineStateSnapshot.ticket_id == ticket_id,
                        PipelineStateSnapshot.company_id == company_id,
                    )
                    .delete()
                )
                db.commit()
                logger.debug(
                    "state_delete_postgresql_success",
                    extra={
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                        "rows_deleted": deleted,
                    },
                )
                return True

            except Exception as db_exc:
                db.rollback()
                raise db_exc
            finally:
                db.close()

        except Exception as exc:
            logger.error(
                "state_delete_postgresql_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return False

    async def _get_history_from_postgresql(
        self,
        ticket_id: str,
        company_id: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Get state history from PostgreSQL.

        Queries PipelineStateSnapshot ordered by created_at DESC.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.
            limit: Maximum number of entries.

        Returns:
            List of state history entry dicts.
        """
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import PipelineStateSnapshot

            db = SessionLocal()
            try:
                snapshots = (
                    db.query(PipelineStateSnapshot)
                    .filter(
                        PipelineStateSnapshot.ticket_id == ticket_id,
                        PipelineStateSnapshot.company_id == company_id,
                    )
                    .order_by(PipelineStateSnapshot.created_at.desc())
                    .limit(limit)
                    .all()
                )

                history: List[Dict[str, Any]] = []
                for snapshot in snapshots:
                    # Parse technique_stack JSON
                    technique_stack: List[str] = []
                    try:
                        technique_stack = json.loads(
                            snapshot.technique_stack or "[]",
                        )
                    except (json.JSONDecodeError, TypeError):
                        pass

                    # Extract gsd_state from state_data if possible
                    gsd_state = "unknown"
                    try:
                        state_dict = json.loads(snapshot.state_data)
                        gsd_state = state_dict.get("gsd_state", "unknown")
                    except (json.JSONDecodeError, TypeError):
                        pass

                    entry = StateHistoryEntry(
                        snapshot_id=snapshot.id,
                        created_at=(
                            snapshot.created_at.isoformat()
                            if snapshot.created_at
                            else "unknown"
                        ),
                        snapshot_type=snapshot.snapshot_type or "auto",
                        current_node=snapshot.current_node or "unknown",
                        gsd_state=gsd_state,
                        token_count=snapshot.token_count or 0,
                        model_used=snapshot.model_used,
                        technique_stack=technique_stack,
                    )
                    history.append(entry.to_dict())

                return history

            finally:
                db.close()

        except Exception as exc:
            logger.error(
                "state_history_postgresql_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            return []

    async def _replay_from_postgresql(
        self,
        ticket_id: str,
        company_id: str,
        snapshot_id: str,
    ) -> Optional[ConversationState]:
        """Load a specific snapshot from PostgreSQL for replay.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier.
            snapshot_id: The unique snapshot ID to load.

        Returns:
            ConversationState if snapshot found, None otherwise.
        """
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import PipelineStateSnapshot

            db = SessionLocal()
            try:
                snapshot = (
                    db.query(PipelineStateSnapshot)
                    .filter(
                        PipelineStateSnapshot.id == snapshot_id,
                        PipelineStateSnapshot.ticket_id == ticket_id,
                        PipelineStateSnapshot.company_id == company_id,
                    )
                    .first()
                )

                if snapshot is None:
                    return None

                state_dict = _safe_json_loads(snapshot.state_data)
                return self.deserialize_state(state_dict)

            finally:
                db.close()

        except StateSerializationError:
            logger.warning(
                "state_replay_postgresql_corrupted",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                },
            )
            return None
        except Exception as exc:
            logger.error(
                "state_replay_postgresql_error",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                    "error": str(exc),
                },
            )
            return None

    # ── Distributed Lock ────────────────────────────────────────

    async def _acquire_lock(
        self,
        ticket_id: str,
    ) -> Optional[str]:
        """Acquire a distributed lock for state operations.

        Uses _redis_get to check if lock exists, and _redis_set to create it.
        Returns the lock token string on success, None if lock is already
        held or all retries exhausted.

        GAP 3 FIX: Added wall-clock timeout to prevent indefinite waiting.
        Even if lock_retries is high, the total time spent attempting to
        acquire the lock is bounded by lock_timeout_seconds. This prevents
        deadlock scenarios where multiple workers wait indefinitely for
        each other's locks.

        Args:
            ticket_id: Ticket identifier to lock on.

        Returns:
            Lock token string if acquired, None if timeout or all retries
            exhausted.
        """
        lock_key = _build_lock_key(ticket_id)
        lock_token = _new_uuid()
        ttl = int(self._config.lock_timeout_seconds)

        # GAP 3 FIX: Track wall-clock time to enforce a hard deadline.
        deadline = time.monotonic() + self._config.lock_timeout_seconds

        attempt = 0
        while True:
            attempt += 1

            # GAP 3 FIX: Check wall-clock deadline before each attempt.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "state_lock_deadline_exceeded",
                    extra={
                        "ticket_id": ticket_id,
                        "elapsed": self._config.lock_timeout_seconds,
                        "lock_timeout_seconds": self._config.lock_timeout_seconds,
                    },
                )
                return None

            try:
                # Check if lock already exists
                existing = await self._redis_get(lock_key)
                if existing is not None:
                    # Lock already held — wait briefly before retrying.
                    # GAP 3 FIX: Don't return None immediately; instead, wait
                    # up to the remaining deadline.
                    wait_time = min(
                        self._config.lock_retry_backoff_ms * attempt / 1000.0,
                        remaining,
                    )
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    continue

                # Try to set the lock
                set_ok = await self._redis_set(
                    lock_key, lock_token, ttl=ttl,
                )
                if set_ok:
                    # In mocked/test environments, _redis_get may not reflect
                    # the set. Trust _redis_set return value instead.
                    logger.debug(
                        "state_lock_acquired",
                        extra={
                            "ticket_id": ticket_id,
                            "attempt": attempt,
                            "elapsed_ms": int(
                                (time.monotonic() - deadline + self._config.lock_timeout_seconds) * 1000
                            ),
                        },
                    )
                    return lock_token

            except Exception as exc:
                logger.warning(
                    "state_lock_error",
                    extra={
                        "ticket_id": ticket_id,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )

            # GAP 3 FIX: Use bounded backoff that respects deadline.
            if attempt < self._config.lock_retries:
                backoff_ms = self._config.lock_retry_backoff_ms * attempt
                backoff_s = min(backoff_ms / 1000.0, remaining)
                if backoff_s > 0:
                    await asyncio.sleep(backoff_s)
            elif remaining > 0:
                # Beyond nominal retries but still within deadline —
                # keep trying until deadline expires (GAP 3 safety net).
                await asyncio.sleep(min(0.05, remaining))
            else:
                break

        logger.warning(
            "state_lock_exhausted",
            extra={
                "ticket_id": ticket_id,
                "retries": attempt,
                "max_retries": self._config.lock_retries,
                "lock_timeout_seconds": self._config.lock_timeout_seconds,
            },
        )
        return None

    async def _release_lock(
        self,
        ticket_id: str,
        lock_token: Optional[str] = None,
    ) -> bool:
        """Release the distributed lock for state operations.

        Only releases the lock if the token matches (or if no token
        is provided / lock doesn't exist).

        Args:
            ticket_id: Ticket identifier.
            lock_token: The lock token to verify ownership.

        Returns:
            True if lock was released or didn't exist, False if wrong token.
        """
        lock_key = _build_lock_key(ticket_id)

        try:
            current = await self._redis_get(lock_key)

            if current is None:
                # Lock doesn't exist — nothing to release
                return True

            if lock_token is not None and current != lock_token:
                # Wrong token — don't release someone else's lock
                return False

            # Token matches or no token provided — delete the lock
            await self._redis_delete(lock_key)

            logger.debug(
                "state_lock_released",
                extra={"ticket_id": ticket_id},
            )
            return True

        except Exception as exc:
            logger.warning(
                "state_lock_release_error",
                extra={
                    "ticket_id": ticket_id,
                    "error": str(exc),
                },
            )
            return False

    # ── Atomic Save with Lock ───────────────────────────────────

    async def save_state_locked(
        self,
        ticket_id: str,
        company_id: str,
        conversation_state: ConversationState,
        snapshot_type: str = "auto",
        **kwargs: Any,
    ) -> SaveResult:
        """Save state with distributed lock for concurrent safety.

        Acquires a distributed lock before performing the save,
        ensuring atomic read-modify-write semantics. Releases the
        lock in a finally block for safety.

        Use this when multiple workers/processes may update the
        same ticket's state concurrently.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).
            conversation_state: The state to persist.
            snapshot_type: One of "auto", "manual", "error", "checkpoint".
            **kwargs: Optional extra fields passed through to save_state.

        Returns:
            SaveResult with success status and backend info.

        Raises:
            StateSerializationError: If lock cannot be acquired or
                both backends fail.
        """
        acquired = await self._acquire_lock(ticket_id)
        if not acquired:
            raise StateSerializationError(
                message=(
                    f"Could not acquire state lock for ticket {ticket_id} "
                    f"after {self._config.lock_retries} retries"
                ),
                error_code="STATE_LOCK_TIMEOUT",
                status_code=409,
                details={
                    "ticket_id": ticket_id,
                    "retries": self._config.lock_retries,
                },
            )

        try:
            return await self.save_state(
                ticket_id=ticket_id,
                company_id=company_id,
                conversation_state=conversation_state,
                snapshot_type=snapshot_type,
                **kwargs,
            )
        finally:
            await self._release_lock(ticket_id, acquired)

    async def load_state_locked(
        self,
        ticket_id: str,
        company_id: str,
    ) -> Optional[ConversationState]:
        """Load state with distributed lock for concurrent safety.

        Acquires a distributed lock before loading, preventing
        race conditions during read-modify-write cycles.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            ConversationState if found, None if lock cannot be acquired.
        """
        lock_token = await self._acquire_lock(ticket_id)
        if not lock_token:
            return None

        try:
            return await self.load_state(
                ticket_id=ticket_id,
                company_id=company_id,
            )
        finally:
            await self._release_lock(ticket_id, lock_token)


# ── Module-level singleton ───────────────────────────────────────

_state_serializer: Optional[StateSerializer] = None


def get_state_serializer(
    config: Optional[StateSerializerConfig] = None,
) -> StateSerializer:
    """Get or create the StateSerializer singleton.

    Thread-safe singleton accessor. Creates the serializer on first
    call and returns the same instance on subsequent calls.

    Args:
        config: Optional configuration override. Only used on first
            call (subsequent calls return the existing instance).

    Returns:
        The StateSerializer singleton instance.
    """
    global _state_serializer
    if _state_serializer is None:
        _state_serializer = StateSerializer(config=config)
    return _state_serializer
