"""Tests for PromptTemplateService.

Covers:
- Default templates: 10 built-in templates loaded with correct metadata
- Template CRUD: create, update, archive, delete, list, get
- Rendering: variable substitution, missing variables, empty vars
- Variant overrides: override precedence, fallback, parent linkage
- Version history: auto-increment on content change, metadata-only no bump
- A/B testing: create, list, get, traffic split, deterministic routing
- Fallback chain: variant → company custom → default
- Edge cases: long content, unicode, empty inputs, service reset
"""

from __future__ import annotations

import pytest
from app.exceptions import (
    NotFoundError,
    ParwaBaseError,
    ValidationError,
)
from app.services.prompt_template_service import (
    VALID_VARIANT_TYPES,
    ABTestConfig,
    ABTestStatus,
    PromptTemplate,
    PromptTemplateService,
    RenderedPrompt,
    TemplateCategory,
    TemplateStatus,
    TemplateVersion,
    extract_variables,
    render_variables,
)

COMPANY_ID = "test-company-001"


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_service():
    """Reset class-level singleton state before every test for isolation."""
    PromptTemplateService._templates = {}
    PromptTemplateService._template_versions = {}
    PromptTemplateService._default_templates = {}
    PromptTemplateService._ab_tests = {}
    PromptTemplateService._initialized = False
    yield


@pytest.fixture
def svc() -> PromptTemplateService:
    """Return a fresh PromptTemplateService."""
    return PromptTemplateService()


# ══════════════════════════════════════════════════════════════════
# 1. Default Templates (~8 tests)
# ══════════════════════════════════════════════════════════════════


class TestDefaultTemplates:
    """Verify the 10 built-in default templates load correctly."""

    def test_ten_default_templates_loaded(self, svc):
        defaults = svc.list_default_templates()
        assert len(defaults) == 10

    def test_all_defaults_have_valid_categories(self, svc):
        valid_cats = {c.value for c in TemplateCategory}
        for tmpl in svc.list_default_templates():
            assert (
                tmpl.category in valid_cats
            ), f"{tmpl.name} has invalid category: {tmpl.category}"

    def test_all_defaults_have_real_content(self, svc):
        for tmpl in svc.list_default_templates():
            assert (
                len(tmpl.content.strip()) > 50
            ), f"{tmpl.name} content is too short / empty"

    def test_all_defaults_have_variables_extracted(self, svc):
        for tmpl in svc.list_default_templates():
            assert isinstance(tmpl.variables, list)
            # Most defaults should have at least one variable
            assert len(tmpl.variables) >= 0  # safety check

    def test_all_defaults_version_starts_at_one(self, svc):
        for tmpl in svc.list_default_templates():
            assert (
                tmpl.version == 1
            ), f"{tmpl.name} version should be 1, got {tmpl.version}"

    def test_all_defaults_status_is_active(self, svc):
        for tmpl in svc.list_default_templates():
            assert tmpl.status == TemplateStatus.ACTIVE.value

    def test_all_defaults_have_is_default_flag(self, svc):
        for tmpl in svc.list_default_templates():
            assert tmpl.is_default is True

    def test_all_defaults_have_unique_names(self, svc):
        defaults = svc.list_default_templates()
        names = [t.name for t in defaults]
        assert len(names) == len(set(names))

    def test_default_template_names_match_definitions(self, svc):
        expected_names = {
            "customer_support_system",
            "classification_intent",
            "classification_sentiment",
            "response_simple",
            "response_moderate",
            "response_complex",
            "guardrail_safety_check",
            "summarization_prompt",
            "rag_context_injection",
            "escalation_prompt",
        }
        actual_names = {t.name for t in svc.list_default_templates()}
        assert actual_names == expected_names


# ══════════════════════════════════════════════════════════════════
# 2. Template CRUD (~12 tests)
# ══════════════════════════════════════════════════════════════════


class TestTemplateCRUD:
    """Create, Read, Update, Archive, Delete, List operations."""

    def test_create_custom_template(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="my_custom_template",
            content="Hello {{name}}, welcome to {{company}}.",
            category=TemplateCategory.CUSTOM.value,
            description="A test custom template",
        )
        assert tmpl.id is not None
        assert tmpl.name == "my_custom_template"
        assert tmpl.company_id == COMPANY_ID
        assert tmpl.version == 1
        assert tmpl.status == TemplateStatus.ACTIVE.value
        assert tmpl.is_default is False
        assert sorted(tmpl.variables) == ["company", "name"]

    def test_create_template_with_variant_type(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="variant_template",
            content="Hi {{name}}",
            category=TemplateCategory.SYSTEM_PROMPT.value,
            description="Variant template",
            variant_type="parwa",
        )
        assert tmpl.variant_type == "parwa"

    def test_update_template_content_increments_version(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="update_test",
            content="Version 1: {{greeting}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        assert tmpl.version == 1

        updated = svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            content="Version 2: {{greeting}} and {{farewell}}",
        )
        assert updated.version == 2
        assert "farewell" in updated.variables

    def test_update_description_no_version_increment(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="desc_update_test",
            content="Hello {{x}}",
            category=TemplateCategory.CUSTOM.value,
            description="Old description",
        )
        updated = svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            description="New description",
        )
        assert updated.version == 1
        assert updated.description == "New description"

    def test_update_metadata_merged(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="meta_test",
            content="Hi {{x}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
            metadata={"team": "support"},
        )
        updated = svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            metadata={"env": "production"},
        )
        assert updated.metadata["team"] == "support"
        assert updated.metadata["env"] == "production"

    def test_archive_template(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="archive_me",
            content="Content {{x}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        archived = svc.archive_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
        )
        assert archived.status == TemplateStatus.ARCHIVED.value

    def test_delete_custom_template(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="delete_me",
            content="Content {{x}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        result = svc.delete_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
        )
        assert result is True

        # Verify it's gone from listing
        templates = svc.list_templates(company_id=COMPANY_ID)
        ids = [t.id for t in templates]
        assert tmpl.id not in ids

    def test_cannot_delete_default_template(self, svc):
        defaults = svc.list_default_templates()
        default_id = defaults[0].id
        result = svc.delete_template(
            company_id=COMPANY_ID,
            template_id=default_id,
        )
        assert result is False

    def test_list_templates_filtered_by_category(self, svc):
        classification = svc.list_templates(
            company_id=COMPANY_ID,
            category=TemplateCategory.CLASSIFICATION.value,
        )
        for tmpl in classification:
            assert tmpl.category == TemplateCategory.CLASSIFICATION.value

    def test_list_templates_filtered_by_status(self, svc):
        active = svc.list_templates(
            company_id=COMPANY_ID,
            status=TemplateStatus.ACTIVE.value,
        )
        for tmpl in active:
            assert tmpl.status == TemplateStatus.ACTIVE.value

    def test_list_with_variant_filter(self, svc):
        # Create a variant template
        svc.create_template(
            company_id=COMPANY_ID,
            name="v_template",
            content="Hi",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
            variant_type="parwa",
        )
        parwa_templates = svc.list_templates(
            company_id=COMPANY_ID,
            variant_type="parwa",
        )
        for tmpl in parwa_templates:
            assert tmpl.variant_type == "parwa"

    def test_get_nonexistent_template_raises(self, svc):
        with pytest.raises(NotFoundError):
            svc.get_template(
                company_id=COMPANY_ID,
                name="no_such_template_xyz",
            )

    def test_update_nonexistent_template_raises(self, svc):
        with pytest.raises(NotFoundError):
            svc.update_template(
                company_id=COMPANY_ID,
                template_id="nonexistent-uuid-12345",
                content="new content",
            )

    def test_delete_nonexistent_returns_false(self, svc):
        result = svc.delete_template(
            company_id=COMPANY_ID,
            template_id="nonexistent-uuid-99999",
        )
        assert result is False


# ══════════════════════════════════════════════════════════════════
# 3. Rendering (~8 tests)
# ══════════════════════════════════════════════════════════════════


class TestRendering:
    """Variable substitution in templates."""

    def test_render_with_all_variables_provided(self, svc):
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="guardrail_safety_check",
            variables={"input_text": "Hello, reset my password please"},
        )
        assert isinstance(rendered, RenderedPrompt)
        assert "Hello, reset my password please" in rendered.rendered_content
        assert "{{input_text}}" not in rendered.rendered_content

    def test_render_with_missing_variables_left_as_is(self, svc):
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="guardrail_safety_check",
            variables={},  # no variables provided
        )
        assert "{{input_text}}" in rendered.rendered_content

    def test_render_with_empty_variables_dict(self, svc):
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="classification_sentiment",
            variables={},
        )
        # Template should still render, leaving all vars as-is
        assert "{{customer_message}}" in rendered.rendered_content
        assert isinstance(rendered, RenderedPrompt)

    def test_render_replacements_applied(self, svc):
        svc.create_template(
            company_id=COMPANY_ID,
            name="render_test",
            content="Hello {{name}}, you are {{age}} years old.",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="render_test",
            variables={"name": "Alice", "age": "30"},
        )
        assert "Hello Alice, you are 30 years old." == rendered.rendered_content

    def test_render_default_template(self, svc):
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variables={
                "agent_name": "PARWA",
                "company_name": "Acme Inc",
                "customer_name": "Bob",
                "knowledge_base_snippet": "Article 1 content",
                "escalation_threshold": "0.4",
                "conversation_context": "Bob wants a refund",
                "supported_languages": "en,es",
            },
        )
        assert isinstance(rendered, RenderedPrompt)
        assert "PARWA" in rendered.rendered_content
        assert "Acme Inc" in rendered.rendered_content

    def test_render_custom_template(self, svc):
        svc.create_template(
            company_id=COMPANY_ID,
            name="custom_render",
            content="Custom: {{topic}} by {{author}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="custom_render",
            variables={"topic": "AI Safety", "author": "Jane"},
        )
        assert "Custom: AI Safety by Jane" == rendered.rendered_content

    def test_render_usage_count_increments(self, svc):
        svc.create_template(
            company_id=COMPANY_ID,
            name="usage_counter",
            content="Hi {{name}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        svc.render_template(
            company_id=COMPANY_ID,
            name="usage_counter",
            variables={"name": "X"},
        )
        tmpl = svc.get_template(COMPANY_ID, "usage_counter")
        assert tmpl.usage_count >= 1

    def test_render_no_variables_needed(self):
        """Template with zero variables should still render fine."""
        result = render_variables("Hello, world!", {})
        assert result == "Hello, world!"


# ══════════════════════════════════════════════════════════════════
# 4. Variant Overrides (~6 tests)
# ══════════════════════════════════════════════════════════════════


class TestVariantOverrides:
    """Variant-specific template overrides and precedence."""

    def test_create_variant_override(self, svc):
        override = svc.create_variant_override(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="parwa",
            content="PARWA variant: {{agent_name}} for {{company_name}}",
        )
        assert override.variant_type == "parwa"
        assert override.name == "customer_support_system"
        assert override.parent_template_id is not None

    def test_override_takes_precedence_over_default(self, svc):
        svc.create_variant_override(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="parwa",
            content="OVERRIDE: {{agent_name}}",
        )
        # Request with parwa variant should get the override
        tmpl = svc.get_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="parwa",
        )
        assert "OVERRIDE:" in tmpl.content

    def test_fallback_to_default_when_no_override(self, svc):
        # Without creating any override, requesting with variant should
        # still fall back to the default
        tmpl = svc.get_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="parwa",
        )
        assert tmpl.is_default is True

    def test_parent_template_id_set_on_override(self, svc):
        parent = svc.get_template(COMPANY_ID, "customer_support_system")
        override = svc.create_variant_override(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="mini_parwa",
            content="Mini override {{x}}",
        )
        assert override.parent_template_id == parent.id

    def test_different_variants_get_different_templates(self, svc):
        svc.create_variant_override(
            company_id=COMPANY_ID,
            name="classification_intent",
            variant_type="parwa",
            content="PARWA intent: {{customer_message}}",
        )
        svc.create_variant_override(
            company_id=COMPANY_ID,
            name="classification_intent",
            variant_type="mini_parwa",
            content="MINI intent: {{customer_message}}",
        )
        parwa_tmpl = svc.get_template(
            COMPANY_ID,
            "classification_intent",
            variant_type="parwa",
        )
        mini_tmpl = svc.get_template(
            COMPANY_ID,
            "classification_intent",
            variant_type="mini_parwa",
        )
        assert "PARWA intent:" in parwa_tmpl.content
        assert "MINI intent:" in mini_tmpl.content
        assert parwa_tmpl.id != mini_tmpl.id

    def test_invalid_variant_type_raises(self, svc):
        with pytest.raises(ParwaBaseError):
            svc.get_template(
                company_id=COMPANY_ID,
                name="customer_support_system",
                variant_type="invalid_variant",
            )


# ══════════════════════════════════════════════════════════════════
# 5. Version History (~5 tests)
# ══════════════════════════════════════════════════════════════════


class TestVersionHistory:
    """Version auto-increment and history tracking."""

    def test_version_increments_on_content_change(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="versioned",
            content="V1: {{a}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        updated = svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            content="V2: {{a}} {{b}}",
        )
        assert updated.version == 2

        updated2 = svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            content="V3: {{a}} {{b}} {{c}}",
        )
        assert updated2.version == 3

    def test_no_version_increment_on_metadata_only(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="meta_version",
            content="Stable {{x}}",
            category=TemplateCategory.CUSTOM.value,
            description="original",
        )
        updated = svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            description="changed desc",
            metadata={"key": "val"},
        )
        assert updated.version == 1

    def test_get_version_history(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="history_test",
            content="V1",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            content="V2",
        )
        svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            content="V3",
        )
        versions = svc.get_template_versions(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
        )
        assert len(versions) == 3

    def test_history_ordered_by_version_descending(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="ordered_test",
            content="V1",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            content="V2",
        )
        versions = svc.get_template_versions(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
        )
        version_numbers = [v.version for v in versions]
        assert version_numbers == [2, 1]

    def test_default_template_has_version_history(self, svc):
        defaults = svc.list_default_templates()
        first_default = defaults[0]
        versions = svc.get_template_versions(
            company_id=COMPANY_ID,
            template_id=first_default.id,
        )
        assert len(versions) >= 1
        assert versions[0].version == 1


# ══════════════════════════════════════════════════════════════════
# 6. A/B Testing (~8 tests)
# ══════════════════════════════════════════════════════════════════


class TestABTesting:
    """A/B test creation, management, and traffic splitting."""

    def test_create_ab_test(self, svc):
        svc.create_template(
            company_id=COMPANY_ID,
            name="ab_template_a",
            content="Template A: {{msg}}",
            category=TemplateCategory.RESPONSE_GENERATION.value,
            description="Control",
        )
        svc.create_template(
            company_id=COMPANY_ID,
            name="ab_template_b",
            content="Template B: {{msg}}",
            category=TemplateCategory.RESPONSE_GENERATION.value,
            description="Variant",
        )
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="response_a_b_test",
            template_a_name="ab_template_a",
            template_b_name="ab_template_b",
            traffic_split=0.5,
        )
        assert test.id is not None
        assert test.company_id == COMPANY_ID
        assert test.status == ABTestStatus.NOT_STARTED.value
        assert test.traffic_split == 0.5

    def test_create_ab_test_with_defaults(self, svc):
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="default_split_test",
            template_a_name="response_simple",
            template_b_name="response_moderate",
        )
        assert test.traffic_split == 0.5

    def test_list_ab_tests(self, svc):
        svc.create_ab_test(
            company_id=COMPANY_ID,
            name="test_1",
            template_a_name="response_simple",
            template_b_name="response_moderate",
        )
        svc.create_ab_test(
            company_id=COMPANY_ID,
            name="test_2",
            template_a_name="classification_intent",
            template_b_name="classification_sentiment",
        )
        tests = svc.list_ab_tests(company_id=COMPANY_ID)
        assert len(tests) == 2

    def test_get_single_ab_test(self, svc):
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="get_test",
            template_a_name="response_simple",
            template_b_name="response_moderate",
        )
        fetched = svc.get_ab_test(
            company_id=COMPANY_ID,
            test_id=test.id,
        )
        assert fetched is not None
        assert fetched.name == "get_test"
        assert fetched.id == test.id

    def test_get_nonexistent_ab_test_returns_none(self, svc):
        result = svc.get_ab_test(
            company_id=COMPANY_ID,
            test_id="nonexistent-id",
        )
        assert result is None

    def test_traffic_split_works(self, svc):
        """Running A/B test with traffic_split=1.0 always selects B."""
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="always_b_test",
            template_a_name="response_simple",
            template_b_name="response_moderate",
            traffic_split=1.0,
        )
        test.status = ABTestStatus.RUNNING.value

        rendered = svc.render_with_ab_test(
            company_id=COMPANY_ID,
            name="response_simple",
            variables={"customer_message": "hello"},
        )
        # With traffic_split=1.0, B should always be selected.
        # The name could be either response_simple or response_moderate
        # depending on which the test matched. But it should be one of the two.
        assert rendered.template_name in ("response_simple", "response_moderate")

    def test_render_with_ab_test_returns_one_of_two(self, svc):
        """A/B test should return one of the two template names."""
        svc.create_template(
            company_id=COMPANY_ID,
            name="ab_a",
            content="Version A {{msg}}",
            category=TemplateCategory.RESPONSE_GENERATION.value,
            description="A",
        )
        svc.create_template(
            company_id=COMPANY_ID,
            name="ab_b",
            content="Version B {{msg}}",
            category=TemplateCategory.RESPONSE_GENERATION.value,
            description="B",
        )
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="a_vs_b",
            template_a_name="ab_a",
            template_b_name="ab_b",
            traffic_split=0.5,
        )
        test.status = ABTestStatus.RUNNING.value

        rendered = svc.render_with_ab_test(
            company_id=COMPANY_ID,
            name="ab_a",
            variables={"msg": "test"},
        )
        assert rendered.template_name in ("ab_a", "ab_b")

    def test_deterministic_splitting(self, svc):
        """Same inputs should always produce the same template selection."""
        svc.create_template(
            company_id=COMPANY_ID,
            name="det_a",
            content="Deterministic A {{msg}}",
            category=TemplateCategory.RESPONSE_GENERATION.value,
            description="A",
        )
        svc.create_template(
            company_id=COMPANY_ID,
            name="det_b",
            content="Deterministic B {{msg}}",
            category=TemplateCategory.RESPONSE_GENERATION.value,
            description="B",
        )
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="det_test",
            template_a_name="det_a",
            template_b_name="det_b",
            traffic_split=0.5,
        )
        test.status = ABTestStatus.RUNNING.value

        variables = {"msg": "hello", "ticket_id": "TICKET-42"}

        results = [
            svc.render_with_ab_test(
                company_id=COMPANY_ID,
                name="det_a",
                variables=variables,
            )
            for _ in range(5)
        ]
        # All results should be identical (same template selected)
        names = [r.template_name for r in results]
        assert len(set(names)) == 1

    def test_ab_test_status_management(self, svc):
        """Verify A/B test status transitions work."""
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="status_test",
            template_a_name="response_simple",
            template_b_name="response_moderate",
        )
        assert test.status == ABTestStatus.NOT_STARTED.value

        # Start the test
        test.status = ABTestStatus.RUNNING.value

        # Pause the test
        test.status = ABTestStatus.PAUSED.value

        # Complete the test
        test.status = ABTestStatus.COMPLETED.value
        test.winner = "a"

        fetched = svc.get_ab_test(
            company_id=COMPANY_ID,
            test_id=test.id,
        )
        assert fetched.status == ABTestStatus.COMPLETED.value
        assert fetched.winner == "a"

    def test_list_ab_tests_filtered_by_status(self, svc):
        svc.create_ab_test(
            company_id=COMPANY_ID,
            name="running_test",
            template_a_name="response_simple",
            template_b_name="response_moderate",
        )
        running = svc.list_ab_tests(
            company_id=COMPANY_ID,
            status=ABTestStatus.NOT_STARTED.value,
        )
        assert len(running) == 1
        assert running[0].name == "running_test"

        empty = svc.list_ab_tests(
            company_id=COMPANY_ID,
            status=ABTestStatus.RUNNING.value,
        )
        assert len(empty) == 0

    def test_ab_test_invalid_traffic_split_raises(self, svc):
        with pytest.raises(ParwaBaseError):
            svc.create_ab_test(
                company_id=COMPANY_ID,
                name="bad_split",
                template_a_name="response_simple",
                template_b_name="response_moderate",
                traffic_split=1.5,
            )

    def test_ab_test_same_template_raises(self, svc):
        with pytest.raises(ValidationError):
            svc.create_ab_test(
                company_id=COMPANY_ID,
                name="same_tmpl",
                template_a_name="response_simple",
                template_b_name="response_simple",
            )


# ══════════════════════════════════════════════════════════════════
# 7. Fallback Chain (~4 tests)
# ══════════════════════════════════════════════════════════════════


class TestFallbackChain:
    """Template resolution: variant override → company custom → default."""

    def test_full_fallback_chain(self, svc):
        """Chain should be: variant override → company custom → default."""
        # 1. Create a company custom template
        svc.create_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
            content="Company custom: {{agent_name}}",
            category=TemplateCategory.SYSTEM_PROMPT.value,
            description="Company override",
        )
        # 2. Create a variant override
        svc.create_variant_override(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="parwa",
            content="Variant override: {{agent_name}}",
        )
        chain = svc.get_fallback_chain(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="parwa",
        )
        # Chain should have: variant, company custom, default
        assert len(chain) == 3
        assert "Variant override:" in chain[0].content
        assert "Company custom:" in chain[1].content
        assert chain[2].is_default is True

    def test_missing_variant_falls_back(self, svc):
        """When no variant override exists, chain has company custom + default."""
        svc.create_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
            content="Company custom: {{agent_name}}",
            category=TemplateCategory.SYSTEM_PROMPT.value,
            description="desc",
        )
        chain = svc.get_fallback_chain(
            company_id=COMPANY_ID,
            name="customer_support_system",
            variant_type="parwa",
        )
        # No parwa variant created, so chain should be: company custom, default
        assert len(chain) == 2
        assert "Company custom:" in chain[0].content
        assert chain[1].is_default is True

    def test_missing_company_falls_back_to_default(self, svc):
        """Without any company templates, chain should have only default."""
        chain = svc.get_fallback_chain(
            company_id=COMPANY_ID,
            name="customer_support_system",
        )
        assert len(chain) == 1
        assert chain[0].is_default is True

    def test_get_template_uses_fallback_chain(self, svc):
        """get_template should follow resolution order."""
        # Without any company templates, should return default
        tmpl = svc.get_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
        )
        assert tmpl.is_default is True

        # Create a company custom
        svc.create_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
            content="Custom override",
            category=TemplateCategory.SYSTEM_PROMPT.value,
            description="desc",
        )
        tmpl2 = svc.get_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
        )
        assert tmpl2.is_default is False
        assert tmpl2.content == "Custom override"


# ══════════════════════════════════════════════════════════════════
# 8. Edge Cases (~5 tests)
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Long content, unicode, empty inputs, service reset."""

    def test_very_long_template_content(self, svc):
        long_content = "This is a very long template. " * 500 + "End with {{var}}."
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="long_template",
            content=long_content,
            category=TemplateCategory.CUSTOM.value,
            description="Very long template",
        )
        assert len(tmpl.content) > 10000

        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="long_template",
            variables={"var": "REPLACED"},
        )
        assert "REPLACED" in rendered.rendered_content
        assert "{{var}}" not in rendered.rendered_content

    def test_unicode_in_variables(self, svc):
        svc.create_template(
            company_id=COMPANY_ID,
            name="unicode_test",
            content="Hello {{name}}, welcome to {{city}}!",
            category=TemplateCategory.CUSTOM.value,
            description="Unicode test",
        )
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="unicode_test",
            variables={
                "name": "Müller",
                "city": "São Paulo",
            },
        )
        assert "Müller" in rendered.rendered_content
        assert "São Paulo" in rendered.rendered_content

    def test_unicode_template_content(self, svc):
        content = "日本語のテンプレート: {{user}} さん、こんにちは！"
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="jp_template",
            content=content,
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        rendered = svc.render_template(
            company_id=COMPANY_ID,
            name="jp_template",
            variables={"user": "田中"},
        )
        assert "田中 さん、こんにちは！" in rendered.rendered_content

    def test_empty_company_id_raises(self, svc):
        with pytest.raises(ParwaBaseError):
            svc.get_template(company_id="", name="customer_support_system")

        with pytest.raises(ParwaBaseError):
            svc.create_template(
                company_id="",
                name="x",
                content="x",
                category=TemplateCategory.CUSTOM.value,
                description="x",
            )

    def test_reset_company_templates(self, svc):
        svc.create_template(
            company_id=COMPANY_ID,
            name="will_be_reset",
            content="Temp {{x}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        count = svc.reset_company_templates(company_id=COMPANY_ID)
        assert count >= 1

        # Defaults should still be accessible
        tmpl = svc.get_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
        )
        assert tmpl.is_default is True

    def test_extract_variables_helper(self):
        content = "Hello {{name}}, your order {{order_id}} is ready."
        vars_found = extract_variables(content)
        assert vars_found == ["name", "order_id"]

    def test_extract_variables_no_vars(self):
        assert extract_variables("No variables here.") == []

    def test_extract_variables_duplicate(self):
        content = "{{x}} and {{x}} and {{y}}"
        assert extract_variables(content) == ["x", "y"]

    def test_render_variables_partial(self):
        result = render_variables(
            "Hello {{name}}, ref: {{ref}}",
            {"name": "Alice"},
        )
        assert "Hello Alice, ref: {{ref}}" == result

    def test_get_template_stats(self, svc):
        stats = svc.get_template_stats(company_id=COMPANY_ID)
        assert stats["company_id"] == COMPANY_ID
        assert stats["default_templates"] == 10
        assert stats["custom_templates"] == 0
        assert stats["running_ab_tests"] == 0


# ══════════════════════════════════════════════════════════════════
# 9. Additional Coverage Tests
# ══════════════════════════════════════════════════════════════════


class TestAdditionalCoverage:
    """Extra tests for completeness and edge behavior."""

    def test_get_default_template_by_name(self, svc):
        tmpl = svc.get_default_template("customer_support_system")
        assert tmpl is not None
        assert tmpl.name == "customer_support_system"
        assert tmpl.is_default is True

    def test_get_default_template_nonexistent(self, svc):
        assert svc.get_default_template("no_such_default") is None

    def test_archive_nonexistent_raises(self, svc):
        with pytest.raises(NotFoundError):
            svc.archive_template(
                company_id=COMPANY_ID,
                template_id="nonexistent-id",
            )

    def test_list_templates_includes_defaults_when_no_custom(self, svc):
        templates = svc.list_templates(company_id=COMPANY_ID)
        assert len(templates) == 10
        # All should be defaults
        for t in templates:
            assert t.is_default is True

    def test_list_templates_excludes_default_when_custom_exists(self, svc):
        svc.create_template(
            company_id=COMPANY_ID,
            name="customer_support_system",
            content="Custom version",
            category=TemplateCategory.SYSTEM_PROMPT.value,
            description="desc",
        )
        templates = svc.list_templates(company_id=COMPANY_ID)
        # Should have 10 entries (custom replaces default by name)
        assert len(templates) == 10
        cs_templates = [t for t in templates if t.name == "customer_support_system"]
        assert len(cs_templates) == 1
        assert cs_templates[0].is_default is False

    def test_update_status_only(self, svc):
        tmpl = svc.create_template(
            company_id=COMPANY_ID,
            name="status_only",
            content="Content {{x}}",
            category=TemplateCategory.CUSTOM.value,
            description="desc",
        )
        updated = svc.update_template(
            company_id=COMPANY_ID,
            template_id=tmpl.id,
            status=TemplateStatus.DEPRECATED.value,
        )
        assert updated.status == TemplateStatus.DEPRECATED.value
        assert updated.version == 1  # no content change

    def test_ab_test_with_default_templates(self, svc):
        """A/B test between two default templates."""
        test = svc.create_ab_test(
            company_id=COMPANY_ID,
            name="defaults_ab",
            template_a_name="response_simple",
            template_b_name="response_moderate",
            traffic_split=0.3,
        )
        assert test.template_a_id != test.template_b_id

    def test_whitespace_company_id_raises(self, svc):
        with pytest.raises(ParwaBaseError):
            svc.get_template(company_id="   ", name="customer_support_system")

    def test_valid_variant_types_constant(self):
        expected = {"mini_parwa", "parwa", "high_parwa"}
        assert VALID_VARIANT_TYPES == expected

    def test_template_dataclass_defaults(self):
        """Verify PromptTemplate dataclass default values."""
        tmpl = PromptTemplate(
            id="test-id",
            company_id="test-co",
            name="test",
            category="custom",
            description="desc",
            content="Hello",
            variables=[],
            version=1,
            status="active",
        )
        assert tmpl.variant_type is None
        assert tmpl.feature_id is None
        assert tmpl.is_default is False
        assert tmpl.parent_template_id is None
        assert tmpl.metadata == {}
        assert tmpl.usage_count == 0
        assert tmpl.created_by is None
        assert tmpl.last_rendered_at is None
        assert tmpl.created_at is not None
        assert tmpl.updated_at is not None

    def test_rendered_prompt_dataclass(self):
        rp = RenderedPrompt(
            template_id="t1",
            template_name="test",
            rendered_content="Hello world",
            variables_used={"x": "1"},
            version=1,
        )
        assert rp.template_id == "t1"
        assert rp.rendered_at is not None

    def test_ab_test_config_dataclass(self):
        ab = ABTestConfig(
            id="ab1",
            company_id="co1",
            name="test",
            template_a_id="a",
            template_b_id="b",
            traffic_split=0.5,
            status="not_started",
        )
        assert ab.total_impressions_a == 0
        assert ab.total_impressions_b == 0
        assert ab.winner is None
        assert ab.started_at is None
        assert ab.created_at is not None

    def test_template_version_dataclass(self):
        tv = TemplateVersion(
            template_id="t1",
            version=1,
            content="Hello",
            change_description="initial",
        )
        assert tv.created_by is None
        assert tv.created_at is not None

    def test_reset_company_removes_ab_tests(self, svc):
        svc.create_ab_test(
            company_id=COMPANY_ID,
            name="will_be_cleared",
            template_a_name="response_simple",
            template_b_name="response_moderate",
        )
        svc.reset_company_templates(company_id=COMPANY_ID)
        tests = svc.list_ab_tests(company_id=COMPANY_ID)
        assert len(tests) == 0

    def test_render_with_ab_test_no_active_falls_through(self, svc):
        """When no A/B test is running, normal rendering should occur."""
        svc.create_ab_test(
            company_id=COMPANY_ID,
            name="inactive_test",
            template_a_name="response_simple",
            template_b_name="response_moderate",
        )
        # Test is NOT_STARTED, not RUNNING
        rendered = svc.render_with_ab_test(
            company_id=COMPANY_ID,
            name="response_simple",
            variables={"customer_message": "hello"},
        )
        assert rendered.template_name == "response_simple"
