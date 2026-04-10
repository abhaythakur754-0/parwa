"""
Tests for Intent Prompt Templates (SG-25)

Covers: 48 templates, intent × response_type coverage,
variant filtering, field population.
"""

import pytest

from app.services.intent_prompt_templates import (
    PromptTemplate,
    PromptTemplateRegistry,
)


# ── Template Count ───────────────────────────────────────────────────


class TestTemplateCount:
    def test_total_templates(self):
        registry = PromptTemplateRegistry()
        assert registry.count_templates() == 48

    def test_12_intents(self):
        registry = PromptTemplateRegistry()
        templates = registry.list_all_templates()
        intents = {t["intent"] for t in templates}
        assert len(intents) == 12

    def test_4_response_types(self):
        registry = PromptTemplateRegistry()
        templates = registry.list_all_templates()
        types = {t["response_type"] for t in templates}
        assert types == {"empathetic", "informational", "resolution", "follow_up"}


# ── Coverage ─────────────────────────────────────────────────────────


class TestCoverage:
    INTENTS = [
        "refund", "technical", "billing", "complaint", "feature_request",
        "general", "cancellation", "shipping", "inquiry", "escalation",
        "account", "feedback",
    ]
    RESPONSE_TYPES = ["empathetic", "informational", "resolution", "follow_up"]

    @pytest.mark.parametrize("intent", INTENTS)
    @pytest.mark.parametrize("response_type", RESPONSE_TYPES)
    def test_every_combination_exists(self, intent, response_type):
        registry = PromptTemplateRegistry()
        template = registry.get_template(intent, response_type, "parwa")
        assert template is not None, f"Missing template: {intent}_{response_type}"


# ── Field Population ─────────────────────────────────────────────────


class TestFieldPopulation:
    def setup_method(self):
        self.registry = PromptTemplateRegistry()

    def test_system_prompt_populated(self):
        template = self.registry.get_template("refund", "empathetic", "parwa")
        assert template is not None
        assert len(template.system_prompt) > 50

    def test_few_shot_examples_populated(self):
        template = self.registry.get_template("refund", "empathetic", "parwa")
        assert template is not None
        assert len(template.few_shot_examples) >= 1
        for example in template.few_shot_examples:
            assert "query" in example
            assert "response" in example

    def test_output_schema_populated(self):
        template = self.registry.get_template("refund", "empathetic", "parwa")
        assert template is not None
        assert "type" in template.output_schema
        assert "properties" in template.output_schema

    def test_tone_instructions_populated(self):
        template = self.registry.get_template("refund", "empathetic", "parwa")
        assert template is not None
        assert len(template.tone_instructions) > 20

    def test_variant_access_populated(self):
        template = self.registry.get_template("refund", "empathetic", "parwa")
        assert template is not None
        assert isinstance(template.variant_access, list)
        assert len(template.variant_access) > 0

    def test_template_id_format(self):
        template = self.registry.get_template("refund", "empathetic", "parwa")
        assert template is not None
        assert template.template_id == "refund_empathetic"


# ── Variant Filtering ───────────────────────────────────────────────


class TestVariantFiltering:
    def setup_method(self):
        self.registry = PromptTemplateRegistry()

    def test_mini_parwa_cannot_get_resolution(self):
        """Mini PARWA should not access resolution templates."""
        template = self.registry.get_template("refund", "resolution", "mini_parwa")
        assert template is None

    def test_mini_parwa_can_get_empathetic(self):
        template = self.registry.get_template("refund", "empathetic", "mini_parwa")
        assert template is not None

    def test_mini_parwa_can_get_informational(self):
        template = self.registry.get_template("refund", "informational", "mini_parwa")
        assert template is not None

    def test_mini_parwa_can_get_follow_up(self):
        template = self.registry.get_template("refund", "follow_up", "mini_parwa")
        assert template is not None

    def test_parwa_gets_resolution(self):
        template = self.registry.get_template("refund", "resolution", "parwa")
        assert template is not None

    def test_parwa_high_gets_resolution(self):
        template = self.registry.get_template("refund", "resolution", "parwa_high")
        assert template is not None

    def test_all_variants_get_empathetic(self):
        for variant in ("mini_parwa", "parwa", "parwa_high"):
            template = self.registry.get_template("billing", "empathetic", variant)
            assert template is not None, f"empathetic not available for {variant}"

    def test_resolution_restricted(self):
        """Resolution templates should exclude mini_parwa."""
        templates = self.registry.list_all_templates()
        resolution = [t for t in templates if t["response_type"] == "resolution"]
        for t in resolution:
            assert "mini_parwa" not in t["variant_access"]


# ── Get Templates for Intent ────────────────────────────────────────


class TestGetTemplatesForIntent:
    def test_refund_has_4_templates(self):
        registry = PromptTemplateRegistry()
        templates = registry.get_templates_for_intent("refund")
        assert len(templates) == 4

    def test_technical_has_4_templates(self):
        registry = PromptTemplateRegistry()
        templates = registry.get_templates_for_intent("technical")
        assert len(templates) == 4

    def test_all_intents_have_4(self):
        registry = PromptTemplateRegistry()
        for intent in [
            "refund", "technical", "billing", "complaint", "feature_request",
            "general", "cancellation", "shipping", "inquiry", "escalation",
            "account", "feedback",
        ]:
            templates = registry.get_templates_for_intent(intent)
            assert len(templates) == 4, f"{intent} has {len(templates)} templates"


# ── List All Templates ──────────────────────────────────────────────


class TestListAllTemplates:
    def test_returns_list(self):
        registry = PromptTemplateRegistry()
        templates = registry.list_all_templates()
        assert isinstance(templates, list)
        assert len(templates) == 48

    def test_has_required_fields(self):
        registry = PromptTemplateRegistry()
        templates = registry.list_all_templates()
        for t in templates:
            assert "template_id" in t
            assert "intent" in t
            assert "response_type" in t
            assert "variant_access" in t


# ── Edge Cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    def test_nonexistent_intent(self):
        registry = PromptTemplateRegistry()
        template = registry.get_template("nonexistent", "empathetic", "parwa")
        assert template is None

    def test_nonexistent_response_type(self):
        registry = PromptTemplateRegistry()
        template = registry.get_template("refund", "nonexistent", "parwa")
        assert template is None

    def test_nonexistent_variant(self):
        registry = PromptTemplateRegistry()
        # Empathetic is available to all, but nonexistent variant
        template = registry.get_template("refund", "resolution", "nonexistent")
        assert template is None
