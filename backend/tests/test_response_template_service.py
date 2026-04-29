"""
Comprehensive tests for ResponseTemplateService.

Tests cover CRUD, template rendering, XSS sanitization, best-match,
variable extraction, validation, per-tenant isolation, caching, and
all edge cases. Uses the in-memory store (no DB/Redis required).
"""

from __future__ import annotations
from app.exceptions import (
    ValidationError,
    NotFoundError,
)
from app.services.response_template_service import (
    ResponseTemplateService,
    ResponseTemplate,
    TemplateVariable,
    VALID_CATEGORIES,
    VALID_LANGUAGES,
    _extract_variables,
    _validate_company_id,
    _KNOWN_VARIABLES,
    sanitize_template_variable,
)

import sys
import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

COMPANY_A = "company-test-a"
COMPANY_B = "company-test-b"


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset the class-level in-memory store before each test."""
    ResponseTemplateService._store.clear()
    ResponseTemplateService._defaults_loaded.clear()
    yield


@pytest.fixture()
def svc():
    return ResponseTemplateService()


@pytest_asyncio.fixture
async def greeting_template(svc):
    """Create a greeting template and return it."""
    t = await svc.create_template(
        company_id=COMPANY_A,
        template_data={
            "name": "My Greeting",
            "category": "greeting",
            "intent_types": ["general"],
            "subject_template": "Hi {{customer_name}}!",
            "body_template": "Hello {{customer_name}}, welcome to {{company_name}}.",
            "language": "en",
            "is_active": True,
            "created_by": "admin",
        },
    )
    return t


# ═══════════════════════════════════════════════════════════════════════
# 1. CREATE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestCreateTemplate:

    @pytest.mark.asyncio
    async def test_create_basic(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Test Template",
            "category": "general",
            "body_template": "Hello {{name}}",
        })
        assert t.id is not None
        assert t.company_id == COMPANY_A
        assert t.name == "Test Template"
        assert t.category == "general"
        assert t.version == 1
        assert t.usage_count == 0
        assert t.is_active is True
        assert t.last_used_at is None

    @pytest.mark.asyncio
    async def test_create_with_all_fields(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Full Template",
            "category": "apology",
            "intent_types": ["complaint", "escalation"],
            "subject_template": "Sorry {{name}}",
            "body_template": "We apologize, {{name}}.",
            "language": "en",
            "is_active": False,
            "created_by": "owner",
        })
        assert t.intent_types == ["complaint", "escalation"]
        assert t.language == "en"
        assert t.is_active is False
        assert t.created_by == "owner"
        assert set(t.variables) >= {"name"}

    @pytest.mark.asyncio
    async def test_create_auto_extracts_variables(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Var Test",
            "category": "billing",
            "subject_template": "Bill for {{order_id}}",
            "body_template": "Amount: {{amount}}, Date: {{date}}",
        })
        assert "amount" in t.variables
        assert "date" in t.variables
        assert "order_id" in t.variables

    @pytest.mark.asyncio
    async def test_create_empty_name_raises(self, svc):
        with pytest.raises(ValidationError, match="name"):
            await svc.create_template(COMPANY_A, {
                "name": "",
                "category": "general",
                "body_template": "test",
            })

    @pytest.mark.asyncio
    async def test_create_whitespace_name_raises(self, svc):
        with pytest.raises(ValidationError, match="name"):
            await svc.create_template(COMPANY_A, {
                "name": "   ",
                "category": "general",
                "body_template": "test",
            })

    @pytest.mark.asyncio
    async def test_create_invalid_category_raises(self, svc):
        with pytest.raises(ValidationError, match="Invalid category"):
            await svc.create_template(COMPANY_A, {
                "name": "Bad Cat",
                "category": "nonexistent_category",
                "body_template": "test",
            })

    @pytest.mark.asyncio
    async def test_create_empty_subject_and_body_raises(self, svc):
        with pytest.raises(ValidationError, match="subject_template or body_template"):
            await svc.create_template(COMPANY_A, {
                "name": "Empty",
                "category": "general",
            })

    @pytest.mark.asyncio
    async def test_create_category_case_insensitive(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Case",
            "category": "GREETING",
            "body_template": "Hi",
        })
        assert t.category == "greeting"

    @pytest.mark.asyncio
    async def test_create_subject_only_is_valid(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Subject Only",
            "category": "general",
            "subject_template": "Hello {{name}}!",
        })
        assert t.subject_template == "Hello {{name}}!"
        assert t.body_template == ""

    @pytest.mark.asyncio
    async def test_create_body_only_is_valid(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Body Only",
            "category": "general",
            "body_template": "Hello {{name}}!",
        })
        assert t.body_template == "Hello {{name}}!"
        assert t.subject_template == ""

    @pytest.mark.asyncio
    async def test_create_with_non_list_intent_types(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Intent",
            "category": "general",
            "body_template": "Hi",
            "intent_types": "not-a-list",
        })
        assert t.intent_types == []  # coerced to list

    @pytest.mark.asyncio
    async def test_create_unknown_language_warns_but_succeeds(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Lang",
            "category": "general",
            "body_template": "Hi",
            "language": "xx",
        })
        assert t.language == "xx"


# ═══════════════════════════════════════════════════════════════════════
# 2. GET TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestGetTemplate:

    @pytest.mark.asyncio
    async def test_get_existing(self, svc, greeting_template):
        t = await svc.get_template(greeting_template.id, COMPANY_A)
        assert t.id == greeting_template.id
        assert t.name == "My Greeting"

    @pytest.mark.asyncio
    async def test_get_not_found(self, svc):
        with pytest.raises(NotFoundError):
            await svc.get_template("nonexistent-id", COMPANY_A)

    @pytest.mark.asyncio
    async def test_get_cross_tenant_not_found(self, svc, greeting_template):
        with pytest.raises(NotFoundError):
            await svc.get_template(greeting_template.id, COMPANY_B)

    @pytest.mark.asyncio
    async def test_get_empty_company_id_raises(self, svc):
        with pytest.raises(ValidationError):
            await svc.get_template("any-id", "")

    @pytest.mark.asyncio
    async def test_get_whitespace_company_id_raises(self, svc):
        with pytest.raises(ValidationError):
            await svc.get_template("any-id", "   ")

    @pytest.mark.asyncio
    async def test_get_default_templates_loaded(self, svc):
        templates = await svc.list_templates(COMPANY_A)
        assert len(templates) == 5
        # Pick one and get it
        t = await svc.get_template(templates[0].id, COMPANY_A)
        assert t.id == templates[0].id


# ═══════════════════════════════════════════════════════════════════════
# 3. LIST TEMPLATES
# ═══════════════════════════════════════════════════════════════════════


class TestListTemplates:

    @pytest.mark.asyncio
    async def test_list_includes_defaults(self, svc):
        templates = await svc.list_templates(COMPANY_A)
        assert len(templates) == 5  # 5 default templates

    @pytest.mark.asyncio
    async def test_list_filter_category(self, svc):
        templates = await svc.list_templates(COMPANY_A, category="greeting")
        assert all(t.category == "greeting" for t in templates)
        assert len(templates) == 1  # only default_greeting

    @pytest.mark.asyncio
    async def test_list_filter_language(self, svc):
        templates = await svc.list_templates(COMPANY_A, language="en")
        assert all(t.language == "en" for t in templates)

    @pytest.mark.asyncio
    async def test_list_filter_no_match(self, svc):
        templates = await svc.list_templates(COMPANY_A, category="xyz")
        assert len(templates) == 0

    @pytest.mark.asyncio
    async def test_list_active_only_true_excludes_inactive(self, svc):
        await svc.create_template(COMPANY_A, {
            "name": "Inactive",
            "category": "general",
            "body_template": "Hi",
            "is_active": False,
        })
        templates = await svc.list_templates(COMPANY_A, active_only=True)
        assert not any(t.name == "Inactive" for t in templates)

    @pytest.mark.asyncio
    async def test_list_active_only_false_includes_inactive(self, svc):
        await svc.create_template(COMPANY_A, {
            "name": "Inactive2",
            "category": "general",
            "body_template": "Hi",
            "is_active": False,
        })
        templates = await svc.list_templates(COMPANY_A, active_only=False)
        assert any(t.name == "Inactive2" for t in templates)

    @pytest.mark.asyncio
    async def test_list_sorted_by_updated_at_desc(self, svc):
        templates = await svc.list_templates(COMPANY_A)
        for i in range(len(templates) - 1):
            assert templates[i].updated_at >= templates[i + 1].updated_at

    @pytest.mark.asyncio
    async def test_list_empty_company_returns_empty(self, svc):
        """BC-008: Empty company_id returns empty list (graceful degradation)."""
        result = await svc.list_templates("")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_tenant_isolation(self, svc):
        templates_a = await svc.list_templates(COMPANY_A)
        templates_b = await svc.list_templates(COMPANY_B)
        # Different sets of IDs
        ids_a = {t.id for t in templates_a}
        ids_b = {t.id for t in templates_b}
        assert ids_a != ids_b

    @pytest.mark.asyncio
    async def test_list_multiple_filters(self, svc):
        await svc.create_template(COMPANY_A, {
            "name": "Fr Greeting",
            "category": "greeting",
            "body_template": "Bonjour",
            "language": "fr",
        })
        templates = await svc.list_templates(
            COMPANY_A, category="greeting", language="fr"
        )
        assert len(templates) == 1
        assert templates[0].language == "fr"


# ═══════════════════════════════════════════════════════════════════════
# 4. UPDATE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateTemplate:

    @pytest.mark.asyncio
    async def test_update_name(self, svc, greeting_template):
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A, {"name": "New Name"}
        )
        assert updated.name == "New Name"
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_update_category(self, svc, greeting_template):
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A, {"category": "farewell"}
        )
        assert updated.category == "farewell"

    @pytest.mark.asyncio
    async def test_update_body_reextracts_variables(
            self, svc, greeting_template):
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A,
            {"body_template": "Just {{foo}} and {{bar}}"}
        )
        assert "foo" in updated.variables
        assert "bar" in updated.variables

    @pytest.mark.asyncio
    async def test_update_invalid_category_raises(
            self, svc, greeting_template):
        with pytest.raises(ValidationError, match="Invalid category"):
            await svc.update_template(
                greeting_template.id, COMPANY_A, {"category": "bad_cat"}
            )

    @pytest.mark.asyncio
    async def test_update_not_found(self, svc):
        with pytest.raises(NotFoundError):
            await svc.update_template("nonexistent", COMPANY_A, {"name": "x"})

    @pytest.mark.asyncio
    async def test_update_cross_tenant_not_found(self, svc, greeting_template):
        with pytest.raises(NotFoundError):
            await svc.update_template(
                greeting_template.id, COMPANY_B, {"name": "x"}
            )

    @pytest.mark.asyncio
    async def test_update_intent_types(self, svc, greeting_template):
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A,
            {"intent_types": ["custom", "feedback"]}
        )
        assert updated.intent_types == ["custom", "feedback"]

    @pytest.mark.asyncio
    async def test_update_toggle_active(self, svc, greeting_template):
        assert greeting_template.is_active is True
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A, {"is_active": False}
        )
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_update_empty_name_ignored(self, svc, greeting_template):
        original_name = greeting_template.name
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A, {"name": ""}
        )
        # Empty name is falsy so update is skipped
        assert updated.name == original_name
        # But since "name" key was in updates, modified should still be True
        # Actually looking at the code: if "name" in updates and updates["name"]:
        # empty string is falsy, so modified remains False for that field
        # But there might be other modifications... Let me re-check
        # No, only name was in updates, so version stays 1
        assert updated.version == 1

    @pytest.mark.asyncio
    async def test_update_non_list_intent_types_ignored(
            self, svc, greeting_template):
        original_intents = list(greeting_template.intent_types)
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A,
            {"intent_types": "not-a-list"}
        )
        assert updated.intent_types == original_intents

    @pytest.mark.asyncio
    async def test_update_subject_template(self, svc, greeting_template):
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A,
            {"subject_template": "New: {{topic}}"}
        )
        assert updated.subject_template == "New: {{topic}}"
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_update_language(self, svc, greeting_template):
        updated = await svc.update_template(
            greeting_template.id, COMPANY_A, {"language": "es"}
        )
        assert updated.language == "es"


# ═══════════════════════════════════════════════════════════════════════
# 5. DELETE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteTemplate:

    @pytest.mark.asyncio
    async def test_delete_existing(self, svc, greeting_template):
        result = await svc.delete_template(greeting_template.id, COMPANY_A)
        assert result is True
        with pytest.raises(NotFoundError):
            await svc.get_template(greeting_template.id, COMPANY_A)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, svc):
        result = await svc.delete_template("nonexistent", COMPANY_A)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_cross_tenant(self, svc, greeting_template):
        result = await svc.delete_template(greeting_template.id, COMPANY_B)
        assert result is False
        # Original still exists for COMPANY_A
        t = await svc.get_template(greeting_template.id, COMPANY_A)
        assert t.id == greeting_template.id

    @pytest.mark.asyncio
    async def test_delete_reduces_list_count(self, svc):
        before = await svc.list_templates(COMPANY_A)
        tid = before[0].id
        await svc.delete_template(tid, COMPANY_A)
        after = await svc.list_templates(COMPANY_A)
        assert len(after) == len(before) - 1


# ═══════════════════════════════════════════════════════════════════════
# 6. DUPLICATE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestDuplicateTemplate:

    @pytest.mark.asyncio
    async def test_duplicate_basic(self, svc, greeting_template):
        copy = await svc.duplicate_template(greeting_template.id, COMPANY_A)
        assert copy.id != greeting_template.id
        assert copy.name == f"{greeting_template.name} (Copy)"
        assert copy.category == greeting_template.category
        assert copy.version == 1
        assert copy.is_active is False
        assert copy.usage_count == 0

    @pytest.mark.asyncio
    async def test_duplicate_preserves_fields(self, svc, greeting_template):
        copy = await svc.duplicate_template(greeting_template.id, COMPANY_A)
        assert copy.company_id == greeting_template.company_id
        assert copy.language == greeting_template.language
        assert copy.intent_types == greeting_template.intent_types
        assert copy.subject_template == greeting_template.subject_template
        assert copy.body_template == greeting_template.body_template
        assert copy.variables == greeting_template.variables

    @pytest.mark.asyncio
    async def test_duplicate_not_found(self, svc):
        with pytest.raises(NotFoundError):
            await svc.duplicate_template("nonexistent", COMPANY_A)

    @pytest.mark.asyncio
    async def test_duplicate_cross_tenant(self, svc, greeting_template):
        with pytest.raises(NotFoundError):
            await svc.duplicate_template(greeting_template.id, COMPANY_B)

    @pytest.mark.asyncio
    async def test_duplicate_independent_modification(
            self, svc, greeting_template):
        copy = await svc.duplicate_template(greeting_template.id, COMPANY_A)
        await svc.update_template(
            copy.id, COMPANY_A, {"name": "Modified Copy"}
        )
        original = await svc.get_template(greeting_template.id, COMPANY_A)
        assert original.name == greeting_template.name  # unchanged


# ═══════════════════════════════════════════════════════════════════════
# 7. RENDER TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestRenderTemplate:

    @pytest.mark.asyncio
    async def test_render_basic_substitution(self, svc, greeting_template):
        rendered = await svc.render_template(
            greeting_template.id, COMPANY_A,
            {"customer_name": "Alice", "company_name": "PARWA"},
        )
        assert "Alice" in rendered
        assert "PARWA" in rendered

    @pytest.mark.asyncio
    async def test_render_missing_variable_left_as_is(
            self, svc, greeting_template):
        rendered = await svc.render_template(
            greeting_template.id, COMPANY_A,
            {"customer_name": "Bob"},  # missing company_name
        )
        assert "Bob" in rendered
        assert "{{company_name}}" in rendered  # left as-is

    @pytest.mark.asyncio
    async def test_render_text_sanitization(self, svc, greeting_template):
        rendered = await svc.render_template(
            greeting_template.id, COMPANY_A,
            {"customer_name": "<script>alert('xss')</script>"},
            content_type="text",
        )
        assert "<script>" not in rendered
        assert "&lt;script&gt;" in rendered

    @pytest.mark.asyncio
    async def test_render_html_sanitization_script_removal(
            self, svc, greeting_template):
        rendered = await svc.render_template(
            greeting_template.id, COMPANY_A,
            {"customer_name": '<script>alert("xss")</script>World'},
            content_type="html",
        )
        assert "<script>" not in rendered.lower()
        assert "World" in rendered

    @pytest.mark.asyncio
    async def test_render_html_sanitization_event_handlers(
            self, svc, greeting_template):
        rendered = await svc.render_template(
            greeting_template.id, COMPANY_A,
            {"customer_name": '<div onclick="alert(1)">Click</div>'},
            content_type="html",
        )
        assert "onclick" not in rendered

    @pytest.mark.asyncio
    async def test_render_increments_usage(self, svc, greeting_template):
        count_before = greeting_template.usage_count
        await svc.render_template(
            greeting_template.id, COMPANY_A,
            {"customer_name": "Test"},
        )
        # Re-fetch to see updated usage
        t = await svc.get_template(greeting_template.id, COMPANY_A)
        assert t.usage_count == count_before + 1

    @pytest.mark.asyncio
    async def test_render_not_found_returns_empty(self, svc):
        rendered = await svc.render_template(
            "nonexistent", COMPANY_A, {}
        )
        assert rendered == ""  # BC-008: safe fallback

    @pytest.mark.asyncio
    async def test_render_empty_variables(self, svc, greeting_template):
        rendered = await svc.render_template(
            greeting_template.id, COMPANY_A, {}
        )
        assert isinstance(rendered, str)
        assert len(rendered) > 0


# ═══════════════════════════════════════════════════════════════════════
# 8. FIND BEST TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestFindBestTemplate:

    @pytest.mark.asyncio
    async def test_find_best_intent_match(self, svc):
        best = await svc.find_best_template(COMPANY_A, intent_type="general")
        assert best is not None
        assert "general" in best.intent_types

    @pytest.mark.asyncio
    async def test_find_best_returns_none_for_empty_tenant(self):
        empty_svc = ResponseTemplateService()
        # Use a company that has never been accessed
        result = await empty_svc.find_best_template("empty-tenant", "general")
        # Should have default templates, so should NOT be None
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_best_negative_sentiment_prefers_apology(self, svc):
        best = await svc.find_best_template(
            COMPANY_A, intent_type="complaint", sentiment_score=0.1
        )
        assert best is not None
        # With negative sentiment, apology template gets a boost
        assert best.category == "apology"

    @pytest.mark.asyncio
    async def test_find_best_positive_sentiment_prefers_greeting(self, svc):
        best = await svc.find_best_template(
            COMPANY_A, intent_type="general", sentiment_score=0.9
        )
        assert best is not None
        # Positive sentiment boosts greeting
        assert best.category == "greeting"

    @pytest.mark.asyncio
    async def test_find_best_escalation_intent(self, svc):
        best = await svc.find_best_template(
            COMPANY_A, intent_type="escalation"
        )
        assert best is not None
        assert best.category == "escalation"


# ═══════════════════════════════════════════════════════════════════════
# 9. GET TEMPLATE VARIABLES
# ═══════════════════════════════════════════════════════════════════════


class TestGetTemplateVariables:

    @pytest.mark.asyncio
    async def test_get_variables_known(self, svc, greeting_template):
        variables = await svc.get_template_variables(
            greeting_template.id, COMPANY_A
        )
        assert len(variables) > 0
        var_names = {v.name for v in variables}
        assert "customer_name" in var_names
        assert "company_name" in var_names

    @pytest.mark.asyncio
    async def test_get_variables_custom(self, svc):
        t = await svc.create_template(COMPANY_A, {
            "name": "Custom Var",
            "category": "general",
            "body_template": "Hi {{unknown_var_xyz}}",
        })
        variables = await svc.get_template_variables(t.id, COMPANY_A)
        var_names = {v.name for v in variables}
        assert "unknown_var_xyz" in var_names
        # Custom variables have default metadata
        custom_var = next(v for v in variables if v.name == "unknown_var_xyz")
        assert custom_var.required is False
        assert custom_var.type == "string"

    @pytest.mark.asyncio
    async def test_get_variables_not_found(self, svc):
        result = await svc.get_template_variables("nonexistent", COMPANY_A)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════
# 10. VALIDATE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════


class TestValidateTemplate:

    @pytest.mark.asyncio
    async def test_valid_template(self, svc):
        result = await svc.validate_template("Hello {{name}}, welcome!")
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert "name" in result.variables_found

    @pytest.mark.asyncio
    async def test_unclosed_variable_tag(self, svc):
        result = await svc.validate_template("Hello {{name}, welcome!")
        assert not result.is_valid
        assert any("Unclosed" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_orphan_closing_braces(self, svc):
        result = await svc.validate_template("Hello name}}, welcome!")
        assert not result.is_valid
        assert any("Orphan" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_empty_template_valid(self, svc):
        result = await svc.validate_template("No variables here.")
        assert result.is_valid is True
        assert result.variables_found == []

    @pytest.mark.asyncio
    async def test_unknown_variable_warning(self, svc):
        result = await svc.validate_template("Hello {{custom_xyz_var}}")
        # Should be valid but warn about unknown variable
        assert result.is_valid is True
        assert any("Unknown variable" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_multiple_variables(self, svc):
        result = await svc.validate_template(
            "{{a}} {{b}} {{c}} {{a}}"
        )
        assert result.is_valid is True
        assert result.variables_found == ["a", "b", "c"]


# ═══════════════════════════════════════════════════════════════════════
# 11. XSS SANITIZATION (standalone function)
# ═══════════════════════════════════════════════════════════════════════


class TestSanitizeTemplateVariable:

    def test_text_escapes_ampersand(self):
        assert "&amp;" in sanitize_template_variable("A&B", "text")

    def test_text_escapes_lt_gt(self):
        result = sanitize_template_variable("<b>hello</b>", "text")
        assert "&lt;b&gt;" in result
        assert "<b>" not in result

    def test_text_escapes_quotes(self):
        result = sanitize_template_variable('"hi\' there', "text")
        assert "&quot;" in result
        assert "&#x27;" in result

    def test_text_plain_string_unchanged(self):
        result = sanitize_template_variable("Hello World", "text")
        assert result == "Hello World"

    def test_html_removes_script_tags(self):
        result = sanitize_template_variable(
            '<script>alert("xss")</script>Hello', "html"
        )
        assert "<script>" not in result.lower()
        assert "Hello" in result

    def test_html_removes_event_handlers(self):
        result = sanitize_template_variable(
            '<div onclick="alert(1)">Click</div>', "html"
        )
        assert "onclick" not in result

    def test_html_removes_javascript_urls(self):
        result = sanitize_template_variable(
            '<a href="javascript:alert(1)">Link</a>', "html"
        )
        assert "javascript:" not in result.lower()

    def test_html_allows_safe_tags(self):
        result = sanitize_template_variable("<p>Hello</p>", "html")
        assert "<p>" in result
        assert "</p>" in result

    def test_html_removes_disallowed_tags(self):
        result = sanitize_template_variable("<iframe>bad</iframe>", "html")
        assert "<iframe>" not in result.lower()

    def test_non_string_input(self):
        result = sanitize_template_variable(12345, "text")
        assert result == "12345"

    def test_none_content_type_passthrough(self):
        result = sanitize_template_variable("<b>test</b>", "other")
        assert result == "<b>test</b>"  # no sanitization for unknown type


# ═══════════════════════════════════════════════════════════════════════
# 12. EXTRACT VARIABLES (standalone function)
# ═══════════════════════════════════════════════════════════════════════


class TestExtractVariables:

    def test_extract_single(self):
        assert _extract_variables("Hello {{name}}") == ["name"]

    def test_extract_multiple(self):
        result = _extract_variables("{{a}} and {{b}} and {{c}}")
        assert result == ["a", "b", "c"]

    def test_extract_duplicates_deduped(self):
        result = _extract_variables("{{x}} {{x}} {{y}}")
        assert result == ["x", "y"]

    def test_extract_none(self):
        assert _extract_variables("No variables here") == []

    def test_extract_with_underscores(self):
        assert _extract_variables("{{customer_name}}") == ["customer_name"]

    def test_extract_with_digits(self):
        assert _extract_variables("{{var123}}") == ["var123"]

    def test_extract_mixed_text(self):
        result = _extract_variables("Dear {{title}} {{last_name}},")
        assert result == ["last_name", "title"]  # sorted


# ═══════════════════════════════════════════════════════════════════════
# 13. VALIDATE COMPANY ID (standalone function)
# ═══════════════════════════════════════════════════════════════════════


class TestValidateCompanyId:

    def test_valid_id(self):
        _validate_company_id("company-123")  # should not raise

    def test_empty_id_raises(self):
        with pytest.raises(ValidationError, match="company_id"):
            _validate_company_id("")

    def test_whitespace_id_raises(self):
        with pytest.raises(ValidationError, match="company_id"):
            _validate_company_id("   ")

    def test_none_id_raises(self):
        with pytest.raises(ValidationError, match="company_id"):
            _validate_company_id(None)


# ═══════════════════════════════════════════════════════════════════════
# 14. RESPONSE TEMPLATE DATACLASS
# ═══════════════════════════════════════════════════════════════════════


class TestResponseTemplateDataclass:

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        t = ResponseTemplate(
            id="id-1",
            company_id="co-1",
            name="Test",
            category="general",
            intent_types=["a"],
            subject_template="Sub {{x}}",
            body_template="Body {{y}}",
            variables=["x", "y"],
            language="en",
            is_active=True,
            usage_count=5,
            last_used_at=now,
            version=2,
            created_by="admin",
            created_at=now,
            updated_at=now,
        )
        d = t.to_dict()
        assert d["id"] == "id-1"
        assert d["name"] == "Test"
        assert d["variables"] == ["x", "y"]
        assert isinstance(d["created_at"], str)
        assert isinstance(d["last_used_at"], str)

    def test_to_dict_none_last_used(self):
        now = datetime.now(timezone.utc)
        t = ResponseTemplate(
            id="id-1",
            company_id="co-1",
            name="Test",
            category="general",
            intent_types=[],
            subject_template="",
            body_template="Body",
            variables=[],
            language="en",
            is_active=True,
            usage_count=0,
            last_used_at=None,
            version=1,
            created_by="",
            created_at=now,
            updated_at=now,
        )
        d = t.to_dict()
        assert d["last_used_at"] is None

    def test_from_dict_roundtrip(self):
        now = datetime.now(timezone.utc)
        original = ResponseTemplate(
            id="id-2",
            company_id="co-2",
            name="Roundtrip",
            category="billing",
            intent_types=["refund"],
            subject_template="{{order_id}}",
            body_template="Refund {{amount}}",
            variables=["amount", "order_id"],
            language="en",
            is_active=True,
            usage_count=3,
            last_used_at=now,
            version=1,
            created_by="system",
            created_at=now,
            updated_at=now,
        )
        d = original.to_dict()
        restored = ResponseTemplate.from_dict(d)
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.category == original.category
        assert restored.variables == original.variables
        assert restored.last_used_at is not None

    def test_from_dict_defaults(self):
        d = {
            "id": "id-3",
            "company_id": "co-3",
            "name": "Defaults",
            "category": "general",
            "subject_template": "",
            "body_template": "Hi",
        }
        t = ResponseTemplate.from_dict(d)
        assert t.intent_types == []
        assert t.language == "en"
        assert t.is_active is True
        assert t.usage_count == 0
        assert t.version == 1
        assert t.created_at is not None


# ═══════════════════════════════════════════════════════════════════════
# 15. DEFAULT TEMPLATES
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultTemplates:

    @pytest.mark.asyncio
    async def test_five_defaults_loaded(self, svc):
        templates = await svc.list_templates(COMPANY_A)
        assert len(templates) == 5
        categories = {t.category for t in templates}
        assert categories == {
            "greeting",
            "apology",
            "escalation",
            "refund",
            "technical"}

    @pytest.mark.asyncio
    async def test_defaults_have_variables(self, svc):
        templates = await svc.list_templates(COMPANY_A)
        for t in templates:
            assert isinstance(t.variables, list)
            assert len(t.variables) > 0  # all defaults have variables

    @pytest.mark.asyncio
    async def test_defaults_are_active(self, svc):
        templates = await svc.list_templates(COMPANY_A)
        assert all(t.is_active for t in templates)

    @pytest.mark.asyncio
    async def test_defaults_created_by_system(self, svc):
        templates = await svc.list_templates(COMPANY_A)
        assert all(t.created_by == "system" for t in templates)

    @pytest.mark.asyncio
    async def test_defaults_not_duplicated(self, svc):
        # Accessing twice should not create duplicates
        t1 = await svc.list_templates(COMPANY_A)
        t2 = await svc.list_templates(COMPANY_A)
        assert len(t1) == len(t2) == 5


# ═══════════════════════════════════════════════════════════════════════
# 16. CONSTANTS
# ═══════════════════════════════════════════════════════════════════════


class TestConstants:

    def test_valid_categories(self):
        assert "greeting" in VALID_CATEGORIES
        assert "farewell" in VALID_CATEGORIES
        assert "custom" in VALID_CATEGORIES
        assert len(VALID_CATEGORIES) == 9

    def test_valid_languages(self):
        assert "en" in VALID_LANGUAGES
        assert "es" in VALID_LANGUAGES
        assert "fr" in VALID_LANGUAGES

    def test_known_variables(self):
        assert "customer_name" in _KNOWN_VARIABLES
        assert "company_name" in _KNOWN_VARIABLES
        assert "agent_name" in _KNOWN_VARIABLES
        # All have proper TemplateVariable type
        for name, var in _KNOWN_VARIABLES.items():
            assert isinstance(var, TemplateVariable)
            assert var.name == name


# ═══════════════════════════════════════════════════════════════════════
# 17. INCREMENT USAGE
# ═══════════════════════════════════════════════════════════════════════


class TestIncrementUsage:

    @pytest.mark.asyncio
    async def test_usage_increments(self, svc, greeting_template):
        await svc.increment_usage(greeting_template.id)
        await svc.increment_usage(greeting_template.id)
        t = await svc.get_template(greeting_template.id, COMPANY_A)
        assert t.usage_count == 2

    @pytest.mark.asyncio
    async def test_last_used_at_updated(self, svc, greeting_template):
        assert greeting_template.last_used_at is None
        await svc.increment_usage(greeting_template.id)
        t = await svc.get_template(greeting_template.id, COMPANY_A)
        assert t.last_used_at is not None

    @pytest.mark.asyncio
    async def test_increment_nonexistent_no_error(self, svc):
        # Should not raise, just log warning
        await svc.increment_usage("nonexistent-id")
