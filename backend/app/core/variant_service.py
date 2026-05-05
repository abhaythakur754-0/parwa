"""
Variant Service: Config resolution for the Variant Engine.

Given a variant_tier + industry (or variant_instance_id), this service
returns the FULL pipeline config — which nodes to run, with what settings,
what model to use, what system prompt, what tools are available.

This is the SINGLE SOURCE OF TRUTH for all variant×industry configurations.
No other module should hardcode variant configs — they all ask this service.

Architecture:
  resolve(tier, industry) → VariantConfig
  resolve_by_instance(instance_id) → VariantConfig (looks up tier + industry)

  VariantConfig contains EVERYTHING the pipeline needs:
    - Which steps to run
    - What LLM model each step should use
    - Token budgets per step
    - System prompts (industry-aware)
    - Available tools (industry-aware)
    - Quality thresholds
    - Cost limits
    - Timeout settings

Design:
  - Configs are built from a 2D matrix: VARIANT_CONFIGS[tier][industry]
  - Industry-specific overrides layer on top of tier defaults
  - Instance-level overrides layer on top of industry configs
  - Priority: instance > industry > tier > global default

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.industry_enum import (
    Industry,
    INDUSTRY_METADATA,
    get_industry_prompt,
    get_industry_tools,
    get_industry_tone,
)
from app.core.variant_router import (
    get_mini_pipeline_steps,
    get_pro_pipeline_steps,
    get_high_pipeline_steps,
    ALL_NODES,
)
from app.logger import get_logger

logger = get_logger("variant_service")


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class StepConfig:
    """Configuration for a single pipeline step within a variant."""

    step_id: str
    enabled: bool = True
    model: str = ""  # LLM model to use (empty = no LLM needed)
    max_tokens: int = 500
    timeout_seconds: float = 5.0
    cost_weight: float = 1.0  # Multiplier for billing


@dataclass
class VariantConfig:
    """Complete configuration for a variant×industry combination.

    This is what the pipeline receives before execution. It tells
    every node exactly how to behave.
    """

    variant_tier: str
    industry: str
    instance_id: str = ""

    # Pipeline topology
    steps: List[str] = field(default_factory=list)
    step_configs: Dict[str, StepConfig] = field(default_factory=dict)

    # Global limits
    max_total_tokens: int = 1000
    max_total_latency_ms: float = 20000.0
    max_cost_usd: float = 0.01

    # Model selection
    classification_model: str = "gpt-4o-mini"
    generation_model: str = "gpt-4o-mini"
    quality_model: str = "gpt-4o-mini"

    # Quality settings
    quality_threshold: float = 0.7  # 0.0-1.0 minimum quality score
    quality_max_retries: int = 1

    # Industry settings
    system_prompt: str = ""
    available_tools: List[str] = field(default_factory=list)
    response_tone: str = "professional_adaptable"

    # Technique settings
    techniques_allowed: List[str] = field(default_factory=list)
    technique_tier_max: int = 1  # 1, 2, or 3

    # Operational
    enable_context_compression: bool = False
    enable_context_health: bool = False
    enable_dedup: bool = False

    # Billing
    cost_per_query_estimate: float = 0.003
    billing_rate_per_1k_tokens: float = 0.00015

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for logging/debugging."""
        return {
            "variant_tier": self.variant_tier,
            "industry": self.industry,
            "instance_id": self.instance_id,
            "steps": list(self.steps),
            "max_total_tokens": self.max_total_tokens,
            "generation_model": self.generation_model,
            "quality_threshold": self.quality_threshold,
            "techniques_allowed": list(self.techniques_allowed),
            "cost_per_query_estimate": self.cost_per_query_estimate,
        }


# ══════════════════════════════════════════════════════════════════
# TIER DEFAULTS
# ══════════════════════════════════════════════════════════════════

# Tier 1 techniques (Mini)
_TIER_1_TECHNIQUES = ["clara", "crp", "gsd"]

# Tier 2 techniques (Pro)
_TIER_2_TECHNIQUES = [
    "chain_of_thought", "reverse_thinking", "react",
    "step_back", "thread_of_thought",
]

# Tier 3 techniques (High)
_TIER_3_TECHNIQUES = [
    "gst", "universe_of_thoughts", "tree_of_thoughts",
    "self_consistency", "reflexion", "least_to_most",
]

TIER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "mini_parwa": {
        "steps": get_mini_pipeline_steps,
        "max_total_tokens": 1000,
        "max_total_latency_ms": 20000.0,
        "max_cost_usd": 0.005,
        "classification_model": "gpt-4o-mini",
        "generation_model": "gpt-4o-mini",
        "quality_model": "gpt-4o-mini",  # not used for Mini but defined for fallback
        "quality_threshold": 0.6,  # lower threshold = less strict
        "quality_max_retries": 0,  # no retries for Mini
        "techniques_allowed": list(_TIER_1_TECHNIQUES),
        "technique_tier_max": 1,
        "enable_context_compression": False,
        "enable_context_health": False,
        "enable_dedup": False,
        "cost_per_query_estimate": 0.003,
        "billing_rate_per_1k_tokens": 0.00015,
    },
    "parwa": {
        "steps": get_pro_pipeline_steps,
        "max_total_tokens": 1500,
        "max_total_latency_ms": 30000.0,
        "max_cost_usd": 0.012,
        "classification_model": "gpt-4o-mini",
        "generation_model": "gpt-4o",
        "quality_model": "gpt-4o-mini",
        "quality_threshold": 0.7,
        "quality_max_retries": 1,
        "techniques_allowed": list(_TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES),
        "technique_tier_max": 2,
        "enable_context_compression": False,
        "enable_context_health": False,
        "enable_dedup": False,
        "cost_per_query_estimate": 0.008,
        "billing_rate_per_1k_tokens": 0.00030,
    },
    "parwa_high": {
        "steps": get_high_pipeline_steps,
        "max_total_tokens": 2000,
        "max_total_latency_ms": 30000.0,
        "max_cost_usd": 0.020,
        "classification_model": "gpt-4o",
        "generation_model": "gpt-4o",
        "quality_model": "gpt-4o",
        "quality_threshold": 0.8,  # highest quality bar
        "quality_max_retries": 1,
        "techniques_allowed": list(
            _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES
        ),
        "technique_tier_max": 3,
        "enable_context_compression": True,
        "enable_context_health": True,
        "enable_dedup": True,
        "cost_per_query_estimate": 0.015,
        "billing_rate_per_1k_tokens": 0.00060,
    },
}


# ══════════════════════════════════════════════════════════════════
# INDUSTRY OVERRIDES
# ══════════════════════════════════════════════════════════════════
# These layer ON TOP of tier defaults.
# Only specify fields that differ from the tier default.

INDUSTRY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    Industry.ECOMMERCE.value: {
        # E-commerce often needs Pro for order tracking + returns
        "mini_parwa": {
            "quality_threshold": 0.65,  # Slightly higher for customer satisfaction
        },
        "parwa": {
            "quality_threshold": 0.75,
        },
        "parwa_high": {
            "quality_threshold": 0.85,
            "enable_context_compression": True,
        },
    },
    Industry.LOGISTICS.value: {
        # Logistics needs precise, factual responses
        "mini_parwa": {
            "quality_threshold": 0.65,
        },
        "parwa": {
            "quality_threshold": 0.75,
        },
        "parwa_high": {
            "quality_threshold": 0.85,
        },
    },
    Industry.SAAS.value: {
        # SaaS often has technical questions needing better models
        "mini_parwa": {
            "classification_model": "gpt-4o-mini",
        },
        "parwa": {
            "classification_model": "gpt-4o-mini",
            "generation_model": "gpt-4o",
        },
        "parwa_high": {
            "classification_model": "gpt-4o",
            "generation_model": "gpt-4o",
        },
    },
    Industry.GENERAL.value: {
        # General uses pure defaults — no overrides needed
    },
}


# ══════════════════════════════════════════════════════════════════
# STEP CONFIGS
# ══════════════════════════════════════════════════════════════════

STEP_DEFAULTS: Dict[str, StepConfig] = {
    "pii_check": StepConfig(
        step_id="pii_check",
        enabled=True,
        model="",  # regex-based, no LLM
        max_tokens=0,
        timeout_seconds=2.0,
        cost_weight=0.0,  # FREE
    ),
    "empathy_check": StepConfig(
        step_id="empathy_check",
        enabled=True,
        model="",  # Can use LLM or sentiment analysis
        max_tokens=50,
        timeout_seconds=2.0,
        cost_weight=0.3,
    ),
    "emergency_check": StepConfig(
        step_id="emergency_check",
        enabled=True,
        model="",  # keyword/regex based, no LLM
        max_tokens=0,
        timeout_seconds=1.0,
        cost_weight=0.0,  # FREE
    ),
    "classify": StepConfig(
        step_id="classify",
        enabled=True,
        model="gpt-4o-mini",  # Overridden by tier config
        max_tokens=100,
        timeout_seconds=3.0,
        cost_weight=0.5,
    ),
    "extract_signals": StepConfig(
        step_id="extract_signals",
        enabled=True,
        model="gpt-4o-mini",
        max_tokens=150,
        timeout_seconds=4.0,
        cost_weight=0.7,
    ),
    "technique_select": StepConfig(
        step_id="technique_select",
        enabled=True,
        model="gpt-4o-mini",
        max_tokens=50,
        timeout_seconds=3.0,
        cost_weight=0.3,
    ),
    "context_compress": StepConfig(
        step_id="context_compress",
        enabled=True,
        model="gpt-4o-mini",
        max_tokens=200,
        timeout_seconds=5.0,
        cost_weight=0.3,
    ),
    "generate": StepConfig(
        step_id="generate",
        enabled=True,
        model="gpt-4o-mini",  # Overridden by tier config
        max_tokens=800,
        timeout_seconds=15.0,
        cost_weight=1.0,
    ),
    "quality_gate": StepConfig(
        step_id="quality_gate",
        enabled=True,
        model="gpt-4o-mini",
        max_tokens=200,
        timeout_seconds=5.0,
        cost_weight=0.5,
    ),
    "context_health": StepConfig(
        step_id="context_health",
        enabled=True,
        model="gpt-4o-mini",
        max_tokens=50,
        timeout_seconds=3.0,
        cost_weight=0.2,
    ),
    "dedup": StepConfig(
        step_id="dedup",
        enabled=True,
        model="",  # embedding similarity, no LLM
        max_tokens=0,
        timeout_seconds=2.0,
        cost_weight=0.1,
    ),
    "format": StepConfig(
        step_id="format",
        enabled=True,
        model="",  # template-based, no LLM
        max_tokens=100,
        timeout_seconds=2.0,
        cost_weight=0.0,  # FREE
    ),
}


# ══════════════════════════════════════════════════════════════════
# VARIANT SERVICE
# ══════════════════════════════════════════════════════════════════


class VariantService:
    """Single source of truth for variant×industry configuration.

    Usage:
        service = VariantService()

        # Resolve by tier + industry
        config = service.resolve("mini_parwa", "ecommerce")

        # Resolve by instance (looks up tier + industry from DB)
        config = service.resolve_by_instance("inst_abc123")

        # Access config fields
        config.steps              → ['pii_check', 'empathy_check', ...]
        config.generation_model   → 'gpt-4o-mini'
        config.system_prompt      → 'You are a customer service...'
        config.available_tools    → ['order_tracker', ...]
    """

    def __init__(self) -> None:
        """Initialize the variant service."""
        logger.info(
            "VariantService initialized — %d tiers, %d industries",
            len(TIER_DEFAULTS),
            len(INDUSTRY_OVERRIDES),
        )

    def resolve(
        self,
        variant_tier: str,
        industry: str = "general",
    ) -> VariantConfig:
        """Resolve full config for a variant_tier + industry combination.

        Priority stack (later overrides earlier):
          1. Global tier defaults (TIER_DEFAULTS)
          2. Industry overrides (INDUSTRY_OVERRIDES)
          3. Instance-level overrides (future: from DB)

        Args:
            variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'.
            industry: 'ecommerce' | 'logistics' | 'saas' | 'general'.

        Returns:
            Fully resolved VariantConfig.
        """
        try:
            # 1. Start with tier defaults
            tier_config = TIER_DEFAULTS.get(
                variant_tier,
                TIER_DEFAULTS["parwa"],  # safe fallback
            )

            # 2. Apply industry overrides
            industry_overrides = INDUSTRY_OVERRIDES.get(industry, {})
            tier_industry_overrides = industry_overrides.get(variant_tier, {})

            # 3. Merge: tier defaults + industry overrides
            merged = {**tier_config, **tier_industry_overrides}

            # 4. Resolve steps (it's a callable in tier defaults)
            steps_fn = merged.get("steps", get_pro_pipeline_steps)
            if callable(steps_fn):
                steps = steps_fn()
            else:
                steps = list(steps_fn)

            # 5. Build step configs (disable steps not in this pipeline)
            step_configs: Dict[str, StepConfig] = {}
            for step_id in ALL_NODES:
                default = STEP_DEFAULTS.get(step_id, StepConfig(step_id=step_id))
                step_configs[step_id] = StepConfig(
                    step_id=step_id,
                    enabled=(step_id in steps),
                    model=merged.get(
                        f"{step_id}_model",
                        default.model,
                    ),
                    max_tokens=default.max_tokens,
                    timeout_seconds=default.timeout_seconds,
                    cost_weight=default.cost_weight,
                )

            # Override classification/generation/quality models from merged config
            if "classification_model" in merged:
                step_configs["classify"].model = merged["classification_model"]
            if "generation_model" in merged:
                step_configs["generate"].model = merged["generation_model"]
            if "quality_model" in merged:
                step_configs["quality_gate"].model = merged["quality_model"]

            # 6. Get industry-specific settings
            system_prompt = get_industry_prompt(industry)
            available_tools = get_industry_tools(industry)
            response_tone = get_industry_tone(industry)

            # 7. Build the final config
            config = VariantConfig(
                variant_tier=variant_tier,
                industry=industry,
                steps=steps,
                step_configs=step_configs,
                max_total_tokens=merged.get("max_total_tokens", 1000),
                max_total_latency_ms=merged.get("max_total_latency_ms", 20000.0),
                max_cost_usd=merged.get("max_cost_usd", 0.01),
                classification_model=merged.get("classification_model", "gpt-4o-mini"),
                generation_model=merged.get("generation_model", "gpt-4o-mini"),
                quality_model=merged.get("quality_model", "gpt-4o-mini"),
                quality_threshold=merged.get("quality_threshold", 0.7),
                quality_max_retries=merged.get("quality_max_retries", 1),
                system_prompt=system_prompt,
                available_tools=available_tools,
                response_tone=response_tone,
                techniques_allowed=merged.get("techniques_allowed", []),
                technique_tier_max=merged.get("technique_tier_max", 1),
                enable_context_compression=merged.get("enable_context_compression", False),
                enable_context_health=merged.get("enable_context_health", False),
                enable_dedup=merged.get("enable_dedup", False),
                cost_per_query_estimate=merged.get("cost_per_query_estimate", 0.003),
                billing_rate_per_1k_tokens=merged.get("billing_rate_per_1k_tokens", 0.00015),
            )

            logger.info(
                "VariantConfig resolved: tier=%s, industry=%s, "
                "steps=%d, model=%s, cost_est=$%.4f",
                variant_tier, industry, len(steps),
                config.generation_model,
                config.cost_per_query_estimate,
            )

            return config

        except Exception:
            logger.exception(
                "VariantService.resolve failed for tier=%s, industry=%s — "
                "returning safe fallback config",
                variant_tier, industry,
            )
            # BC-008: Return a safe minimal config
            return VariantConfig(
                variant_tier=variant_tier or "mini_parwa",
                industry=industry or "general",
                steps=get_mini_pipeline_steps(),
                max_total_tokens=500,
                generation_model="gpt-4o-mini",
                cost_per_query_estimate=0.003,
                system_prompt=get_industry_prompt("general"),
                available_tools=get_industry_tools("general"),
                response_tone="professional_adaptable",
            )

    def resolve_by_instance(
        self,
        company_id: str,
        instance_id: str,
    ) -> VariantConfig:
        """Resolve config by looking up instance details from DB.

        1. Look up instance_id → variant_tier, industry
        2. Call resolve(tier, industry) for base config
        3. Apply instance-level overrides (from DB)

        Args:
            company_id: Tenant identifier (BC-001).
            instance_id: Variant instance identifier.

        Returns:
            Fully resolved VariantConfig with instance overrides.
        """
        try:
            # Future: Look up instance from database
            # instance = VariantInstance.query.filter_by(
            #     id=instance_id, company_id=company_id
            # ).first()

            # For now, use the tier + industry resolution
            # This will be enhanced when we wire the DB layer
            logger.info(
                "resolve_by_instance: instance_id=%s, company_id=%s "
                "(using tier+industry resolution — DB lookup coming soon)",
                instance_id, company_id,
            )

            # Fallback: return general config for parwa tier
            return self.resolve("parwa", "general")

        except Exception:
            logger.exception(
                "resolve_by_instance failed for company_id=%s, "
                "instance_id=%s — returning safe fallback",
                company_id, instance_id,
            )
            return self.resolve("mini_parwa", "general")

    def get_all_configs(self) -> Dict[str, Dict[str, VariantConfig]]:
        """Get all variant×industry configurations.

        Useful for the management UI to display the full config matrix.

        Returns:
            Dict[variant_tier][industry] = VariantConfig
        """
        try:
            result: Dict[str, Dict[str, VariantConfig]] = {}
            for tier in TIER_DEFAULTS:
                result[tier] = {}
                for industry in [i.value for i in Industry]:
                    result[tier][industry] = self.resolve(tier, industry)
            return result
        except Exception:
            logger.exception("get_all_configs failed — returning empty dict")
            return {}

    def get_config_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all configs for dashboard display.

        Returns:
            List of dicts with key config fields per tier×industry.
        """
        try:
            summary = []
            for tier in TIER_DEFAULTS:
                for industry in [i.value for i in Industry]:
                    config = self.resolve(tier, industry)
                    summary.append({
                        "variant_tier": tier,
                        "industry": industry,
                        "steps_count": len(config.steps),
                        "steps": config.steps,
                        "generation_model": config.generation_model,
                        "max_tokens": config.max_total_tokens,
                        "quality_threshold": config.quality_threshold,
                        "techniques_count": len(config.techniques_allowed),
                        "cost_estimate": config.cost_per_query_estimate,
                        "tools_count": len(config.available_tools),
                    })
            return summary
        except Exception:
            logger.exception("get_config_summary failed — returning empty list")
            return []
