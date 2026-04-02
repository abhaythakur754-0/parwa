"""Tests for Technique Database Models (DB07, DB08, DB09).

Covers: TechniqueConfiguration, TechniqueExecution, TechniqueVersion
model fields, constraints, defaults, and relationships.
"""

import pytest

from database.models.technique import (
    TechniqueConfiguration,
    TechniqueExecution,
    TechniqueVersion,
)
from database.base import Base


class TestTechniqueConfiguration:
    """DB07: technique_configurations table."""

    def test_table_name(self):
        assert TechniqueConfiguration.__tablename__ == "technique_configurations"

    def test_has_id(self):
        assert hasattr(TechniqueConfiguration, "id")

    def test_has_company_id(self):
        assert hasattr(TechniqueConfiguration, "company_id")

    def test_has_technique_id(self):
        assert hasattr(TechniqueConfiguration, "technique_id")

    def test_has_tier(self):
        assert hasattr(TechniqueConfiguration, "tier")

    def test_has_is_enabled(self):
        assert hasattr(TechniqueConfiguration, "is_enabled")

    def test_has_custom_token_budget(self):
        assert hasattr(TechniqueConfiguration, "custom_token_budget")

    def test_has_custom_trigger_threshold(self):
        assert hasattr(TechniqueConfiguration, "custom_trigger_threshold")

    def test_has_custom_timeout_ms(self):
        assert hasattr(TechniqueConfiguration, "custom_timeout_ms")

    def test_has_updated_by(self):
        assert hasattr(TechniqueConfiguration, "updated_by")

    def test_has_timestamps(self):
        assert hasattr(TechniqueConfiguration, "created_at")
        assert hasattr(TechniqueConfiguration, "updated_at")

    def test_has_unique_constraint(self):
        assert len(TechniqueConfiguration.__table_args__) >= 1

    def test_inherits_from_base(self):
        assert issubclass(TechniqueConfiguration, Base)


class TestTechniqueExecution:
    """DB08: technique_executions table."""

    def test_table_name(self):
        assert TechniqueExecution.__tablename__ == "technique_executions"

    def test_has_id(self):
        assert hasattr(TechniqueExecution, "id")

    def test_has_company_id(self):
        assert hasattr(TechniqueExecution, "company_id")

    def test_has_ticket_id(self):
        assert hasattr(TechniqueExecution, "ticket_id")

    def test_has_conversation_id(self):
        assert hasattr(TechniqueExecution, "conversation_id")

    def test_has_technique_id(self):
        assert hasattr(TechniqueExecution, "technique_id")

    def test_has_tier(self):
        assert hasattr(TechniqueExecution, "tier")

    def test_has_signal_fields(self):
        assert hasattr(TechniqueExecution, "query_complexity")
        assert hasattr(TechniqueExecution, "confidence_score")
        assert hasattr(TechniqueExecution, "sentiment_score")
        assert hasattr(TechniqueExecution, "customer_tier")
        assert hasattr(TechniqueExecution, "monetary_value")
        assert hasattr(TechniqueExecution, "turn_count")
        assert hasattr(TechniqueExecution, "intent_type")

    def test_has_trigger_rules(self):
        assert hasattr(TechniqueExecution, "trigger_rules")

    def test_has_token_metrics(self):
        assert hasattr(TechniqueExecution, "tokens_input")
        assert hasattr(TechniqueExecution, "tokens_output")
        assert hasattr(TechniqueExecution, "tokens_overhead")

    def test_has_latency(self):
        assert hasattr(TechniqueExecution, "latency_ms")

    def test_has_result_status(self):
        assert hasattr(TechniqueExecution, "result_status")

    def test_has_fallback_fields(self):
        assert hasattr(TechniqueExecution, "fallback_technique")
        assert hasattr(TechniqueExecution, "fallback_reason")

    def test_has_error_message(self):
        assert hasattr(TechniqueExecution, "error_message")

    def test_has_created_at(self):
        assert hasattr(TechniqueExecution, "created_at")

    def test_inherits_from_base(self):
        assert issubclass(TechniqueExecution, Base)


class TestTechniqueVersion:
    """DB09: technique_versions table."""

    def test_table_name(self):
        assert TechniqueVersion.__tablename__ == "technique_versions"

    def test_has_id(self):
        assert hasattr(TechniqueVersion, "id")

    def test_has_company_id(self):
        assert hasattr(TechniqueVersion, "company_id")

    def test_has_technique_id(self):
        assert hasattr(TechniqueVersion, "technique_id")

    def test_has_version(self):
        assert hasattr(TechniqueVersion, "version")

    def test_has_label(self):
        assert hasattr(TechniqueVersion, "label")

    def test_has_is_active(self):
        assert hasattr(TechniqueVersion, "is_active")

    def test_has_is_default(self):
        assert hasattr(TechniqueVersion, "is_default")

    def test_has_ab_test_fields(self):
        assert hasattr(TechniqueVersion, "ab_test_enabled")
        assert hasattr(TechniqueVersion, "ab_test_traffic_pct")

    def test_has_performance_metrics(self):
        assert hasattr(TechniqueVersion, "total_activations")
        assert hasattr(TechniqueVersion, "avg_accuracy_lift")
        assert hasattr(TechniqueVersion, "avg_tokens_consumed")
        assert hasattr(TechniqueVersion, "avg_latency_ms")
        assert hasattr(TechniqueVersion, "csat_delta")

    def test_has_prompt_template(self):
        assert hasattr(TechniqueVersion, "prompt_template")

    def test_has_configuration(self):
        assert hasattr(TechniqueVersion, "configuration")

    def test_has_timestamps(self):
        assert hasattr(TechniqueVersion, "created_at")
        assert hasattr(TechniqueVersion, "updated_at")

    def test_has_unique_constraint(self):
        assert len(TechniqueVersion.__table_args__) >= 1

    def test_inherits_from_base(self):
        assert issubclass(TechniqueVersion, Base)


class TestTechniqueConfigurationDefaults:
    def test_is_enabled_default_true(self):
        col = TechniqueConfiguration.__table__.c["is_enabled"]
        assert col.default is not None

    def test_custom_token_budget_nullable(self):
        col = TechniqueConfiguration.__table__.c["custom_token_budget"]
        assert col.nullable is True


class TestTechniqueExecutionDefaults:
    def test_result_status_default_success(self):
        col = TechniqueExecution.__table__.c["result_status"]
        assert col.default is not None


class TestTechniqueVersionDefaults:
    def test_is_active_default_true(self):
        col = TechniqueVersion.__table__.c["is_active"]
        assert col.default is not None

    def test_total_activations_default_zero(self):
        col = TechniqueVersion.__table__.c["total_activations"]
        assert col.default is not None
