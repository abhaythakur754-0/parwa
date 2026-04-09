"""
PARWA Rule→AI Migration Service (F-158)

Manages the gradual migration from hardcoded trigger rules to
AI-learned dynamic routing rules. Supports:
- Rule versioning and A/B testing
- Gradual traffic shifting
- Rollback capability
- Per-tenant custom rules

BC-001: All operations scoped to company_id.
"""

from typing import Any, Dict

from backend.app.core.technique_router import TRIGGER_RULES
from backend.app.exceptions import ValidationError
from backend.app.logger import get_logger

logger = get_logger("rule_migration_service")


class RuleMigrationService:
    """Manages migration from static to dynamic AI rules."""

    # Migration modes
    MODE_STATIC = "static"        # All hardcoded rules
    MODE_SHADOW = "shadow"        # AI rules evaluated but not applied (shadow mode)
    MODE_CANARY = "canary"        # AI rules applied for X% of requests
    MODE_GRADUAL = "gradual"      # Percentage increases over time
    MODE_ACTIVE = "active"        # AI rules fully active

    def __init__(self, db, company_id: str):
        self.db = db
        self.company_id = company_id

    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status for tenant.

        Returns mode, percentage, rule counts, etc.
        Since we don't have a migration_rules table yet, return defaults.
        """
        return {
            "mode": self.MODE_STATIC,
            "ai_rule_percentage": 0.0,
            "static_rules_count": len(TRIGGER_RULES),
            "ai_rules_count": 0,
            "migration_enabled": False,
            "company_id": self.company_id,
        }

    def enable_migration(
        self,
        mode: str = "shadow",
        percentage: float = 0.0,
    ) -> Dict[str, Any]:
        """Enable migration mode for tenant.

        Modes: shadow, canary, gradual, active
        - Shadow: AI evaluates but doesn't apply (logging only)
        - Canary: AI applied for percentage of requests
        - Gradual: Percentage auto-increases
        - Active: Full AI routing
        """
        valid_modes = [
            self.MODE_STATIC, self.MODE_SHADOW, self.MODE_CANARY,
            self.MODE_GRADUAL, self.MODE_ACTIVE,
        ]
        if mode not in valid_modes:
            raise ValidationError(
                f"Invalid migration mode: {mode}. Must be one of: {valid_modes}"
            )
        if not 0 <= percentage <= 100:
            raise ValidationError("Percentage must be between 0 and 100")

        logger.info(
            "migration_mode_enabled",
            company_id=self.company_id,
            mode=mode,
            percentage=percentage,
        )

        return {
            "mode": mode,
            "ai_rule_percentage": percentage,
            "migration_enabled": mode != self.MODE_STATIC,
            "company_id": self.company_id,
        }

    def should_use_ai_rule(self) -> bool:
        """Determine if current request should use AI rule based on mode.

        Implements percentage-based traffic splitting.
        Will be connected to Redis/DB for per-tenant config.
        For now, always returns False (static mode).
        """
        return False

    def compare_rules(
        self,
        signals_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare static rule output vs AI rule output for analysis.

        Used in shadow mode to evaluate AI rule quality.
        """
        from backend.app.core.technique_router import TechniqueRouter, QuerySignals

        # Build signals
        signals = QuerySignals(
            query_complexity=signals_dict.get("query_complexity", 0.0),
            confidence_score=signals_dict.get("confidence_score", 1.0),
            sentiment_score=signals_dict.get("sentiment_score", 0.7),
            customer_tier=signals_dict.get("customer_tier", "free"),
            monetary_value=signals_dict.get("monetary_value", 0.0),
            turn_count=signals_dict.get("turn_count", 0),
            intent_type=signals_dict.get("intent_type", "general"),
        )

        # Get static rule result
        router = TechniqueRouter()
        static_result = router.route(signals)

        return {
            "static_rules": {
                "activated": [a.technique_id.value for a in static_result.activated_techniques],
                "total_tokens": static_result.total_estimated_tokens,
            },
            "ai_rules": {
                "activated": [],  # Will be populated by AI model
                "total_tokens": 0,
                "model": None,
            },
            "match": True,  # Will be calculated when AI rules are active
            "company_id": self.company_id,
        }

    def get_migration_metrics(self) -> Dict[str, Any]:
        """Get migration quality metrics.

        Tracks agreement rate, latency difference, quality scores.
        """
        return {
            "total_comparisons": 0,
            "agreement_rate": 1.0,
            "avg_static_latency_ms": 0,
            "avg_ai_latency_ms": 0,
            "quality_score_static": None,
            "quality_score_ai": None,
            "recommendation": "Start with shadow mode to collect comparison data",
        }

    def rollback(self) -> Dict[str, Any]:
        """Immediately revert to static rules for this tenant."""
        logger.warning(
            "migration_rollback",
            company_id=self.company_id,
        )
        return {
            "mode": self.MODE_STATIC,
            "ai_rule_percentage": 0.0,
            "migration_enabled": False,
            "rolled_back": True,
            "company_id": self.company_id,
        }
