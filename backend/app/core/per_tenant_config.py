"""
Per-Tenant Configuration Management (Week 10 Day 3).

Manages per-company configuration overrides for the PARWA AI engine.
Configuration is stored in-memory (simulates DB / Redis) with thread-safe
access via threading.RLock.

Categories:
  - technique:  Technique enable/disable, thresholds, token budget
  - compression: Strategy, level, max tokens
  - workflow:   Variant type, human checkpoints, concurrency
  - model:      Model tier, temperature, fallback

Features:
  - Default config per variant type (mini_parwa, parwa, parwa_high)
  - Per-company overrides merged with defaults
  - Config validation with type checking
  - Config versioning (change history)
  - Config change notifications (callback registry)
  - Config export / import (JSON)
  - Thread-safe with RLock

BC-001: All configs scoped by company_id.
"""

import copy
import json
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("per_tenant_config")


# ── Configuration Dataclasses ────────────────────────────────────


@dataclass
class TenantTechniqueConfig:
    """Technique-level configuration for a tenant."""

    enabled_techniques: List[str] = field(default_factory=list)
    disabled_techniques: List[str] = field(default_factory=list)
    custom_thresholds: Dict[str, float] = field(default_factory=dict)
    token_budget_override: Optional[int] = None


@dataclass
class TenantCompressionConfig:
    """Compression-level configuration for a tenant."""

    strategy: str = "hybrid"
    level: str = "moderate"
    max_tokens: int = 4000
    preserve_recent_n: int = 3


@dataclass
class TenantWorkflowConfig:
    """Workflow-level configuration for a tenant."""

    variant_type: str = "parwa"
    enable_human_checkpoint: bool = True
    checkpoint_timeout_seconds: float = 300.0
    max_concurrent_workflows: int = 5


@dataclass
class TenantModelConfig:
    """Model-preference configuration for a tenant."""

    preferred_model_tier: str = "medium"
    temperature: float = 0.3
    max_tokens: int = 4096
    fallback_enabled: bool = True


@dataclass
class TenantFullConfig:
    """Complete merged configuration for a tenant."""

    technique: TenantTechniqueConfig = field(
        default_factory=TenantTechniqueConfig
    )
    compression: TenantCompressionConfig = field(
        default_factory=TenantCompressionConfig
    )
    workflow: TenantWorkflowConfig = field(
        default_factory=TenantWorkflowConfig
    )
    model: TenantModelConfig = field(
        default_factory=TenantModelConfig
    )


# ── Validation Schemas ───────────────────────────────────────────

_TECHNIQUE_SCHEMA: Dict[str, Any] = {
    "enabled_techniques": list,
    "disabled_techniques": list,
    "custom_thresholds": dict,
    "token_budget_override": (type(None), int),
}

_COMPRESSION_SCHEMA: Dict[str, Any] = {
    "strategy": str,
    "level": str,
    "max_tokens": int,
    "preserve_recent_n": int,
}

_WORKFLOW_SCHEMA: Dict[str, Any] = {
    "variant_type": str,
    "enable_human_checkpoint": bool,
    "checkpoint_timeout_seconds": (int, float),
    "max_concurrent_workflows": int,
}

_MODEL_SCHEMA: Dict[str, Any] = {
    "preferred_model_tier": str,
    "temperature": (int, float),
    "max_tokens": int,
    "fallback_enabled": bool,
}

CATEGORY_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "technique": _TECHNIQUE_SCHEMA,
    "compression": _COMPRESSION_SCHEMA,
    "workflow": _WORKFLOW_SCHEMA,
    "model": _MODEL_SCHEMA,
}

VALID_STRATEGIES = {"hybrid", "priority_based", "extractive", "sliding_window"}
VALID_LEVELS = {"none", "light", "moderate", "aggressive"}
VALID_VARIANT_TYPES = {"mini_parwa", "parwa", "parwa_high"}
VALID_MODEL_TIERS = {"light", "medium", "heavy"}


# ── Default Configurations per Variant ───────────────────────────


def _mini_parwa_defaults() -> TenantFullConfig:
    """Default config for mini_parwa variant."""
    return TenantFullConfig(
        technique=TenantTechniqueConfig(
            enabled_techniques=["keyword_extract", "intent_classify"],
            disabled_techniques=[
                "chain_of_thought", "reflexion", "self_critique"
            ],
            custom_thresholds={},
            token_budget_override=500,
        ),
        compression=TenantCompressionConfig(
            strategy="extractive",
            level="aggressive",
            max_tokens=1500,
            preserve_recent_n=2,
        ),
        workflow=TenantWorkflowConfig(
            variant_type="mini_parwa",
            enable_human_checkpoint=False,
            checkpoint_timeout_seconds=120.0,
            max_concurrent_workflows=10,
        ),
        model=TenantModelConfig(
            preferred_model_tier="light",
            temperature=0.1,
            max_tokens=1024,
            fallback_enabled=False,
        ),
    )


def _parwa_defaults() -> TenantFullConfig:
    """Default config for parwa variant."""
    return TenantFullConfig(
        technique=TenantTechniqueConfig(
            enabled_techniques=[
                "keyword_extract", "intent_classify",
                "chain_of_thought", "self_critique",
            ],
            disabled_techniques=["reflexion"],
            custom_thresholds={},
            token_budget_override=1500,
        ),
        compression=TenantCompressionConfig(
            strategy="hybrid",
            level="moderate",
            max_tokens=4000,
            preserve_recent_n=3,
        ),
        workflow=TenantWorkflowConfig(
            variant_type="parwa",
            enable_human_checkpoint=True,
            checkpoint_timeout_seconds=300.0,
            max_concurrent_workflows=5,
        ),
        model=TenantModelConfig(
            preferred_model_tier="medium",
            temperature=0.3,
            max_tokens=4096,
            fallback_enabled=True,
        ),
    )


def _parwa_high_defaults() -> TenantFullConfig:
    """Default config for parwa_high variant."""
    return TenantFullConfig(
        technique=TenantTechniqueConfig(
            enabled_techniques=[
                "keyword_extract", "intent_classify",
                "chain_of_thought", "reflexion", "self_critique",
            ],
            disabled_techniques=[],
            custom_thresholds={
                "confidence_threshold": 0.95,
            },
            token_budget_override=3000,
        ),
        compression=TenantCompressionConfig(
            strategy="priority_based",
            level="light",
            max_tokens=8000,
            preserve_recent_n=5,
        ),
        workflow=TenantWorkflowConfig(
            variant_type="parwa_high",
            enable_human_checkpoint=True,
            checkpoint_timeout_seconds=600.0,
            max_concurrent_workflows=2,
        ),
        model=TenantModelConfig(
            preferred_model_tier="heavy",
            temperature=0.5,
            max_tokens=8192,
            fallback_enabled=True,
        ),
    )


VARIANT_DEFAULTS: Dict[str, Callable[[], TenantFullConfig]] = {
    "mini_parwa": _mini_parwa_defaults,
    "parwa": _parwa_defaults,
    "parwa_high": _parwa_high_defaults,
}


# ── Change Notification ─────────────────────────────────────────

ChangeCallback = Callable[[str, str, Dict[str, Any]], None]


# ── Version History Entry ────────────────────────────────────────


@dataclass
class ConfigVersionEntry:
    """Single entry in the config version history."""

    version: int
    category: str
    timestamp: str
    changes: Dict[str, Any]


# ── Validation Result ───────────────────────────────────────────


@dataclass
class ValidationResult:
    """Result of config validation."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ── TenantConfigManager ─────────────────────────────────────────


class TenantConfigManager:
    """Per-tenant configuration manager.

    Stores tenant configuration in-memory with thread-safe access.
    Supports per-company overrides merged with variant defaults.

    BC-001: All configurations scoped by company_id.

    Args:
        default_variant: Default variant type for new tenants.
    """

    def __init__(self, default_variant: str = "parwa") -> None:
        """Initialize the configuration manager.

        Args:
            default_variant: Default variant type for new tenants
                without explicit config. Must be one of
                VALID_VARIANT_TYPES.
        """
        if default_variant not in VALID_VARIANT_TYPES:
            raise ValueError(
                f"Invalid default_variant: {default_variant}. "
                f"Must be one of {VALID_VARIANT_TYPES}"
            )

        self._default_variant = default_variant
        self._lock = threading.RLock()

        # company_id -> {category -> config_dict}
        self._overrides: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # company_id -> version counter
        self._versions: Dict[str, int] = {}

        # company_id -> list of version entries
        self._version_history: Dict[
            str, List[ConfigVersionEntry]
        ] = {}

        # Registered change callbacks
        self._change_callbacks: List[ChangeCallback] = []

        # Track which variant each tenant is based on
        self._tenant_variants: Dict[str, str] = {}

    # ── Core CRUD ───────────────────────────────────────────────

    def get_config(self, company_id: str) -> TenantFullConfig:
        """Get the merged configuration for a tenant.

        Merges variant defaults with per-company overrides.
        Overrides take precedence over defaults.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Fully merged TenantFullConfig instance.
        """
        with self._lock:
            if company_id not in self._overrides:
                # No overrides — return default variant config
                defaults = VARIANT_DEFAULTS[self._default_variant]()
                return defaults

            overrides = self._overrides[company_id]
            variant = self._tenant_variants.get(
                company_id, self._default_variant
            )
            base = VARIANT_DEFAULTS[variant]()

            # Deep copy to avoid mutating shared defaults
            merged = copy.deepcopy(base)

            if "technique" in overrides:
                merged.technique = self._apply_overrides_dataclass(
                    merged.technique, overrides["technique"],
                    TenantTechniqueConfig,
                )
            if "compression" in overrides:
                merged.compression = self._apply_overrides_dataclass(
                    merged.compression, overrides["compression"],
                    TenantCompressionConfig,
                )
            if "workflow" in overrides:
                merged.workflow = self._apply_overrides_dataclass(
                    merged.workflow, overrides["workflow"],
                    TenantWorkflowConfig,
                )
            if "model" in overrides:
                merged.model = self._apply_overrides_dataclass(
                    merged.model, overrides["model"],
                    TenantModelConfig,
                )

            return merged

    def update_config(
        self,
        company_id: str,
        category: str,
        config_dict: Dict[str, Any],
    ) -> TenantFullConfig:
        """Update a single config category for a tenant.

        Validates the config_dict before applying. Triggers
        change notifications on success.

        Args:
            company_id: Tenant identifier (BC-001).
            category: One of "technique", "compression",
                "workflow", "model".
            config_dict: Partial or full config dict to apply.

        Returns:
            Updated TenantFullConfig after merge.

        Raises:
            ValueError: If category is invalid or validation fails.
        """
        if category not in CATEGORY_SCHEMAS:
            raise ValueError(
                f"Invalid category: {category}. "
                f"Must be one of {list(CATEGORY_SCHEMAS.keys())}"
            )

        # Validate
        validation = self.validate_config(category, config_dict)
        if not validation.valid:
            raise ValueError(
                f"Config validation failed: {validation.errors}"
            )

        with self._lock:
            if company_id not in self._overrides:
                self._overrides[company_id] = {}
                self._versions[company_id] = 0
                self._version_history[company_id] = []
                self._tenant_variants[company_id] = (
                    self._default_variant
                )

            # Check for variant_type change in workflow category
            if category == "workflow" and "variant_type" in config_dict:
                new_variant = config_dict["variant_type"]
                if new_variant in VALID_VARIANT_TYPES:
                    self._tenant_variants[company_id] = new_variant

            self._overrides[company_id][category] = copy.deepcopy(
                config_dict
            )

            # Version tracking
            self._versions[company_id] += 1
            version = self._versions[company_id]

            entry = ConfigVersionEntry(
                version=version,
                category=category,
                timestamp=datetime.now(timezone.utc).isoformat(),
                changes=copy.deepcopy(config_dict),
            )
            self._version_history[company_id].append(entry)

            merged = self.get_config(company_id)

            # Notify callbacks (outside lock for safety)
            self._notify_change(company_id, category, config_dict)

            return merged

    def reset_to_defaults(
        self,
        company_id: str,
        category: Optional[str] = None,
    ) -> TenantFullConfig:
        """Reset tenant config to defaults.

        Args:
            company_id: Tenant identifier.
            category: If provided, only reset this category.
                If None, reset all categories.

        Returns:
            Config after reset.
        """
        with self._lock:
            if category is not None:
                if category not in CATEGORY_SCHEMAS:
                    raise ValueError(
                        f"Invalid category: {category}. "
                        f"Must be one of "
                        f"{list(CATEGORY_SCHEMAS.keys())}"
                    )
                if company_id in self._overrides:
                    self._overrides[company_id].pop(category, None)
                    if not self._overrides[company_id]:
                        self._overrides.pop(company_id, None)
                        self._versions.pop(company_id, None)
                        self._version_history.pop(
                            company_id, None
                        )
                        self._tenant_variants.pop(
                            company_id, None
                        )
            else:
                self._overrides.pop(company_id, None)
                self._versions.pop(company_id, None)
                self._version_history.pop(company_id, None)
                self._tenant_variants.pop(company_id, None)

            return self.get_config(company_id)

    def get_defaults(
        self, variant_type: str,
    ) -> TenantFullConfig:
        """Get default configuration for a variant type.

        Args:
            variant_type: One of VALID_VARIANT_TYPES.

        Returns:
            Fresh copy of the default TenantFullConfig.

        Raises:
            ValueError: If variant_type is invalid.
        """
        if variant_type not in VARIANT_DEFAULTS:
            raise ValueError(
                f"Invalid variant_type: {variant_type}. "
                f"Must be one of {VALID_VARIANT_TYPES}"
            )
        return VARIANT_DEFAULTS[variant_type]()

    # ── Validation ──────────────────────────────────────────────

    def validate_config(
        self,
        category: str,
        config_dict: Dict[str, Any],
    ) -> ValidationResult:
        """Validate a config dict against the category schema.

        Checks:
        - Category is known
        - All keys are valid for the category
        - Value types match the schema
        - Enum values are valid (strategy, level, variant_type, etc.)

        Args:
            category: Config category name.
            config_dict: Config to validate.

        Returns:
            ValidationResult with errors and warnings.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if category not in CATEGORY_SCHEMAS:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown category: {category}"],
            )

        schema = CATEGORY_SCHEMAS[category]

        for key, value in config_dict.items():
            if key not in schema:
                errors.append(f"Unknown field '{key}' in {category}")
                continue

            expected = schema[key]
            if not isinstance(value, expected):
                errors.append(
                    f"Field '{key}' expected {expected}, "
                    f"got {type(value).__name__}"
                )

        # Enum value validation
        if category == "compression":
            if "strategy" in config_dict:
                if config_dict["strategy"] not in VALID_STRATEGIES:
                    errors.append(
                        f"Invalid strategy: "
                        f"{config_dict['strategy']}. "
                        f"Must be one of {VALID_STRATEGIES}"
                    )
            if "level" in config_dict:
                if config_dict["level"] not in VALID_LEVELS:
                    errors.append(
                        f"Invalid level: "
                        f"{config_dict['level']}. "
                        f"Must be one of {VALID_LEVELS}"
                    )

        if category == "workflow":
            if "variant_type" in config_dict:
                vt = config_dict["variant_type"]
                if vt not in VALID_VARIANT_TYPES:
                    errors.append(
                        f"Invalid variant_type: {vt}. "
                        f"Must be one of "
                        f"{VALID_VARIANT_TYPES}"
                    )

        if category == "model":
            if "preferred_model_tier" in config_dict:
                tier = config_dict["preferred_model_tier"]
                if tier not in VALID_MODEL_TIERS:
                    errors.append(
                        f"Invalid preferred_model_tier: {tier}. "
                        f"Must be one of {VALID_MODEL_TIERS}"
                    )
            if "temperature" in config_dict:
                temp = config_dict["temperature"]
                if isinstance(temp, (int, float)):
                    if not (0.0 <= temp <= 2.0):
                        warnings.append(
                            f"Temperature {temp} is outside "
                            f"recommended range [0.0, 2.0]"
                        )

        # Positive value checks
        if category == "compression":
            if "max_tokens" in config_dict:
                if config_dict["max_tokens"] <= 0:
                    errors.append(
                        "max_tokens must be positive"
                    )
            if "preserve_recent_n" in config_dict:
                if config_dict["preserve_recent_n"] < 0:
                    errors.append(
                        "preserve_recent_n must be >= 0"
                    )

        if category == "workflow":
            if "max_concurrent_workflows" in config_dict:
                mcw = config_dict["max_concurrent_workflows"]
                if mcw <= 0:
                    errors.append(
                        "max_concurrent_workflows "
                        "must be positive"
                    )
            if "checkpoint_timeout_seconds" in config_dict:
                cts = config_dict[
                    "checkpoint_timeout_seconds"
                ]
                if cts <= 0:
                    errors.append(
                        "checkpoint_timeout_seconds "
                        "must be positive"
                    )

        if category == "model":
            if "max_tokens" in config_dict:
                if config_dict["max_tokens"] <= 0:
                    errors.append("max_tokens must be positive")

        if category == "technique":
            if "token_budget_override" in config_dict:
                tbo = config_dict["token_budget_override"]
                if tbo is not None and tbo < 0:
                    errors.append(
                        "token_budget_override must be "
                        ">= 0 or None"
                    )
            if "custom_thresholds" in config_dict:
                for tid, val in config_dict[
                    "custom_thresholds"
                ].items():
                    if not isinstance(val, (int, float)):
                        errors.append(
                            f"Threshold for '{tid}' must be "
                            f"a number"
                        )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ── Export / Import ─────────────────────────────────────────

    def export_config(self, company_id: str) -> str:
        """Export tenant configuration as JSON string.

        Args:
            company_id: Tenant identifier.

        Returns:
            JSON string with exported configuration.
        """
        with self._lock:
            config = self.get_config(company_id)
            export_data = {
                "company_id": company_id,
                "variant_type": self._tenant_variants.get(
                    company_id, self._default_variant
                ),
                "overrides": copy.deepcopy(
                    self._overrides.get(company_id, {})
                ),
                "version": self._versions.get(company_id, 0),
                "full_config": asdict(config),
            }
            return json.dumps(export_data, indent=2, default=str)

    def import_config(
        self,
        company_id: str,
        json_str: str,
    ) -> ValidationResult:
        """Import tenant configuration from JSON string.

        Validates all categories before applying. Does NOT
        replace existing config if validation fails.

        Args:
            company_id: Tenant identifier.
            json_str: JSON string with configuration data.

        Returns:
            ValidationResult indicating success or failure.
        """
        all_errors: List[str] = []
        all_warnings: List[str] = []

        try:
            data = json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as exc:
            return ValidationResult(
                valid=False,
                errors=[f"Invalid JSON: {exc}"],
            )

        if not isinstance(data, dict):
            return ValidationResult(
                valid=False,
                errors=["Import data must be a JSON object"],
            )

        # Extract overrides or full_config
        overrides = data.get("overrides", {})
        full_config = data.get("full_config", {})

        # Use overrides if present, otherwise extract from
        # full_config categories
        categories_to_import: Dict[str, Dict[str, Any]] = {}
        if overrides and isinstance(overrides, dict):
            categories_to_import = overrides
        elif full_config and isinstance(full_config, dict):
            for cat in CATEGORY_SCHEMAS:
                if cat in full_config:
                    categories_to_import[cat] = full_config[cat]

        # Validate all categories
        for cat, cat_config in categories_to_import.items():
            if not isinstance(cat_config, dict):
                all_errors.append(
                    f"Category '{cat}' must be a dict"
                )
                continue
            result = self.validate_config(cat, cat_config)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        if all_errors:
            return ValidationResult(
                valid=False,
                errors=all_errors,
                warnings=all_warnings,
            )

        # Apply all validated configs
        with self._lock:
            if company_id not in self._overrides:
                self._overrides[company_id] = {}
                self._versions[company_id] = 0
                self._version_history[company_id] = []
                self._tenant_variants[company_id] = (
                    self._default_variant
                )

            for cat, cat_config in categories_to_import.items():
                self._overrides[company_id][cat] = (
                    copy.deepcopy(cat_config)
                )

                # Handle variant_type change
                if (
                    cat == "workflow"
                    and "variant_type" in cat_config
                ):
                    vt = cat_config["variant_type"]
                    if vt in VALID_VARIANT_TYPES:
                        self._tenant_variants[
                            company_id
                        ] = vt

                self._versions[company_id] += 1
                self._version_history[company_id].append(
                    ConfigVersionEntry(
                        version=self._versions[company_id],
                        category=cat,
                        timestamp=(
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                        ),
                        changes=copy.deepcopy(cat_config),
                    )
                )

        return ValidationResult(
            valid=True,
            errors=[],
            warnings=all_warnings,
        )

    # ── Version History ─────────────────────────────────────────

    def get_version_history(
        self, company_id: str,
    ) -> List[Dict[str, Any]]:
        """Get configuration change history for a tenant.

        Args:
            company_id: Tenant identifier.

        Returns:
            List of version entry dicts with version, category,
            timestamp, and changes.
        """
        with self._lock:
            history = self._version_history.get(company_id, [])
            return [asdict(entry) for entry in history]

    # ── Tenant Listing ──────────────────────────────────────────

    def list_tenants(self) -> List[str]:
        """List all tenant IDs with configurations.

        Returns:
            Sorted list of company_id strings.
        """
        with self._lock:
            return sorted(self._overrides.keys())

    # ── Change Notifications ────────────────────────────────────

    def on_config_change(self, callback: ChangeCallback) -> None:
        """Register a callback for config changes.

        Callbacks receive (company_id, category, changes_dict).

        Args:
            callback: Function to call on config change.
        """
        self._change_callbacks.append(callback)

    def remove_config_change_callback(
        self, callback: ChangeCallback,
    ) -> bool:
        """Remove a registered change callback.

        Args:
            callback: The callback to remove.

        Returns:
            True if removed, False if not found.
        """
        try:
            self._change_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    # ── Internal Helpers ────────────────────────────────────────

    @staticmethod
    def _apply_overrides_dataclass(
        base: Any,
        overrides: Dict[str, Any],
        cls: type,
    ) -> Any:
        """Apply a dict of overrides to a dataclass instance.

        Only applies keys that exist in the dataclass. Returns
        a new instance.

        Args:
            base: Existing dataclass instance.
            overrides: Dict of field -> new value.
            cls: Dataclass type to instantiate.

        Returns:
            New dataclass instance with overrides applied.
        """
        current = asdict(base)
        for key, value in overrides.items():
            if key in current:
                current[key] = value
        return cls(**current)

    def _notify_change(
        self,
        company_id: str,
        category: str,
        changes: Dict[str, Any],
    ) -> None:
        """Fire all registered change callbacks.

        Callbacks are called outside the lock to prevent
        deadlocks. Errors in callbacks are caught and logged
        but do not interrupt the config update.
        """
        for cb in self._change_callbacks:
            try:
                cb(company_id, category, changes)
            except Exception as exc:
                logger.error(
                    "config_change_callback_error",
                    extra={
                        "company_id": company_id,
                        "category": category,
                        "error": str(exc),
                    },
                )
