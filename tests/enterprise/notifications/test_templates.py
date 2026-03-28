# Tests for Week 48 Builder 4 - Template Engine
# Unit tests for template_engine.py, template_variables.py, template_localization.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from enterprise.notifications.template_engine import (
    TemplateEngine,
    Template,
    TemplateFormat,
    TemplateCategory,
    RenderedContent
)

from enterprise.notifications.template_variables import (
    VariableManager,
    VariableDefinition,
    VariableType,
    VariableContext
)

from enterprise.notifications.template_localization import (
    LocalizationManager,
    Locale,
    LocalizedTemplate
)


# ============== TEMPLATE ENGINE TESTS ==============

class TestTemplateEngine:
    def test_create_template(self):
        engine = TemplateEngine()
        template = engine.create_template(
            tenant_id="t1",
            name="welcome",
            content="Hello {{name}}, welcome!"
        )
        assert template.tenant_id == "t1"
        assert template.name == "welcome"
        assert "name" in template.variables

    def test_create_template_with_subject(self):
        engine = TemplateEngine()
        template = engine.create_template(
            tenant_id="t1",
            name="email",
            subject="Welcome {{name}}",
            content="Hello {{name}}!"
        )
        assert template.subject is not None
        assert "name" in template.variables

    def test_render_template(self):
        engine = TemplateEngine()
        template = engine.create_template(
            tenant_id="t1",
            name="greeting",
            content="Hello {{name}}!"
        )
        rendered = engine.render(template.id, {"name": "John"})
        assert rendered.content == "Hello John!"

    def test_render_with_defaults(self):
        engine = TemplateEngine()
        template = engine.create_template(
            tenant_id="t1",
            name="test",
            content="Hello {{name}}!",
            default_values={"name": "Guest"}
        )
        rendered = engine.render(template.id, {})
        assert rendered.content == "Hello Guest!"

    def test_render_with_filter(self):
        engine = TemplateEngine()
        template = engine.create_template(
            tenant_id="t1",
            name="test",
            content="Hello {{name|upper}}!"
        )
        rendered = engine.render(template.id, {"name": "john"})
        assert rendered.content == "Hello JOHN!"

    def test_render_subject(self):
        engine = TemplateEngine()
        template = engine.create_template(
            tenant_id="t1",
            name="email",
            subject="Welcome {{name}}",
            content="Body"
        )
        rendered = engine.render(template.id, {"name": "John"})
        assert rendered.subject == "Welcome John"

    def test_get_template(self):
        engine = TemplateEngine()
        template = engine.create_template("t1", "test", "Content")
        result = engine.get_template(template.id)
        assert result.id == template.id

    def test_get_template_by_name(self):
        engine = TemplateEngine()
        engine.create_template("t1", "welcome", "Content")
        result = engine.get_template_by_name("t1", "welcome")
        assert result is not None
        assert result.name == "welcome"

    def test_update_template(self):
        engine = TemplateEngine()
        template = engine.create_template("t1", "test", "Old content")
        updated = engine.update_template(template.id, content="New content")
        assert updated.content == "New content"
        assert updated.version == 2

    def test_delete_template(self):
        engine = TemplateEngine()
        template = engine.create_template("t1", "test", "Content")
        result = engine.delete_template(template.id)
        assert result is True
        assert engine.get_template(template.id) is None

    def test_get_templates_by_tenant(self):
        engine = TemplateEngine()
        engine.create_template("t1", "test1", "C1")
        engine.create_template("t1", "test2", "C2")
        engine.create_template("t2", "test3", "C3")
        results = engine.get_templates_by_tenant("t1")
        assert len(results) == 2

    def test_validate_template_valid(self):
        engine = TemplateEngine()
        result = engine.validate_template("Hello {{name}}!")
        assert result["valid"] is True

    def test_validate_template_unclosed_tag(self):
        engine = TemplateEngine()
        result = engine.validate_template("Hello {{name!")
        assert result["valid"] is False

    def test_nested_variable(self):
        engine = TemplateEngine()
        template = engine.create_template(
            tenant_id="t1",
            name="test",
            content="Hello {{user.name}}!"
        )
        rendered = engine.render(template.id, {"user": {"name": "John"}})
        assert rendered.content == "Hello John!"

    def test_register_custom_filter(self):
        engine = TemplateEngine()
        engine.register_filter("double", lambda x: str(x) * 2)
        template = engine.create_template(
            tenant_id="t1",
            name="test",
            content="{{name|double}}"
        )
        rendered = engine.render(template.id, {"name": "Hi"})
        assert rendered.content == "HiHi"


# ============== TEMPLATE VARIABLES TESTS ==============

class TestVariableManager:
    def test_get_definition(self):
        manager = VariableManager()
        definition = manager.get_definition("user.name")
        assert definition is not None
        assert definition.var_type == VariableType.STRING

    def test_get_all_definitions(self):
        manager = VariableManager()
        definitions = manager.get_all_definitions()
        assert len(definitions) > 0

    def test_validate_variable_valid(self):
        manager = VariableManager()
        result = manager.validate_variable("user.email", "test@example.com")
        assert result["valid"] is True

    def test_validate_variable_invalid_email(self):
        manager = VariableManager()
        result = manager.validate_variable("user.email", "invalid-email")
        assert result["valid"] is False

    def test_validate_variable_unknown(self):
        manager = VariableManager()
        result = manager.validate_variable("unknown.var", "value")
        assert result["valid"] is True  # Unknown vars are valid with warning
        assert len(result["warnings"]) > 0

    def test_register_definition(self):
        manager = VariableManager()
        definition = VariableDefinition(
            name="custom.field",
            var_type=VariableType.STRING,
            description="Custom field"
        )
        manager.register_definition(definition)
        result = manager.get_definition("custom.field")
        assert result is not None

    def test_apply_transform_upper(self):
        manager = VariableManager()
        result = manager.apply_transform("hello", "upper")
        assert result == "HELLO"

    def test_apply_transform_lower(self):
        manager = VariableManager()
        result = manager.apply_transform("HELLO", "lower")
        assert result == "hello"

    def test_apply_transform_currency(self):
        manager = VariableManager()
        result = manager.apply_transform(123.45, "currency")
        assert result == "$123.45"

    def test_apply_transform_percentage(self):
        manager = VariableManager()
        result = manager.apply_transform(0.75, "percentage")
        assert result == "75.0%"

    def test_build_context(self):
        manager = VariableManager()
        context = manager.build_context("t1", "u1", {"custom": "value"})
        assert context["tenant"]["id"] == "t1"
        assert context["user"]["id"] == "u1"
        assert context["custom"] == "value"

    def test_merge_contexts(self):
        manager = VariableManager()
        base = {"user": {"name": "John"}, "value": 1}
        override = {"user": {"email": "john@example.com"}, "value": 2}
        result = manager.merge_contexts(base, override)
        assert result["user"]["name"] == "John"
        assert result["user"]["email"] == "john@example.com"
        assert result["value"] == 2

    def test_extract_variables_from_template(self):
        manager = VariableManager()
        template = "Hello {{user.name}}, your order {{order_id}} is ready."
        variables = manager.extract_variables_from_template(template)
        assert len(variables) == 2

    def test_register_custom_transform(self):
        manager = VariableManager()
        manager.register_transform("reverse", lambda x: str(x)[::-1])
        result = manager.apply_transform("hello", "reverse")
        assert result == "olleh"


# ============== TEMPLATE LOCALIZATION TESTS ==============

class TestLocalizationManager:
    def test_get_locale(self):
        manager = LocalizationManager()
        locale = manager.get_locale("en-US")
        assert locale is not None
        assert locale.language == "en"

    def test_get_all_locales(self):
        manager = LocalizationManager()
        locales = manager.get_all_locales()
        assert len(locales) >= 10  # At least default locales

    def test_get_locales_by_language(self):
        manager = LocalizationManager()
        locales = manager.get_locales_by_language("en")
        assert len(locales) >= 2  # en-US and en-GB

    def test_create_localized_template(self):
        manager = LocalizationManager()
        localized = manager.create_localized_template(
            template_id="template1",
            locale_code="es-ES",
            content="¡Hola {{nombre}}!"
        )
        assert localized.locale_code == "es-ES"

    def test_get_localized_template(self):
        manager = LocalizationManager()
        manager.create_localized_template(
            template_id="template1",
            locale_code="es-ES",
            content="Hola"
        )
        result = manager.get_localized_template("template1", "es-ES")
        assert result is not None

    def test_get_best_template_fallback(self):
        manager = LocalizationManager()
        manager.create_localized_template(
            template_id="template1",
            locale_code="en-US",
            content="Hello"
        )
        manager.create_localized_template(
            template_id="template1",
            locale_code="es-ES",
            content="Hola"
        )
        result = manager.get_best_template("template1", ["fr-FR", "en-US"])
        assert result.locale_code == "en-US"

    def test_add_translation(self):
        manager = LocalizationManager()
        manager.add_translation("greeting.hello", "es-ES", "Hola")
        result = manager.get_translation("greeting.hello", "es-ES")
        assert result == "Hola"

    def test_translate_with_fallback(self):
        manager = LocalizationManager()
        manager.add_translation("greeting.hello", "en-US", "Hello")
        result = manager.translate("greeting.hello", "fr-FR", "Hi")
        assert result == "Hello"  # Falls back to en-US

    def test_translate_missing(self):
        manager = LocalizationManager()
        result = manager.translate("missing.key", "en-US", "Default")
        assert result == "Default"

    def test_format_date(self):
        manager = LocalizationManager()
        date = datetime(2024, 3, 15)
        result = manager.format_date(date, "en-US")
        assert "03" in result or "3" in result

    def test_format_date_with_time(self):
        manager = LocalizationManager()
        dt = datetime(2024, 3, 15, 14, 30)
        result = manager.format_date(dt, "en-US", include_time=True)
        assert result  # Should have date and time

    def test_format_number(self):
        manager = LocalizationManager()
        result = manager.format_number(1234567.89, "en-US")
        assert "1,234,567" in result

    def test_format_currency(self):
        manager = LocalizationManager()
        result = manager.format_currency(99.99, "en-US")
        assert "$99.99" in result

    def test_format_currency_euro(self):
        manager = LocalizationManager()
        result = manager.format_currency(99.99, "de-DE")
        assert "99,99" in result  # German uses comma for decimal

    def test_detect_locale_from_header(self):
        manager = LocalizationManager()
        result = manager.detect_locale_from_accept_language("es-ES,en;q=0.9")
        assert result == "es-ES"

    def test_detect_locale_fallback(self):
        manager = LocalizationManager()
        result = manager.detect_locale_from_accept_language("")
        assert result == "en-US"

    def test_rtl_locale(self):
        manager = LocalizationManager()
        locale = manager.get_locale("ar-SA")
        assert locale.rtl is True

    def test_export_import_translations(self):
        manager = LocalizationManager()
        manager.add_translation("key1", "es-ES", "valor1")
        manager.add_translation("key2", "es-ES", "valor2")

        exported = manager.export_translations("es-ES")
        assert "key1" in exported

        # Import to new locale
        count = manager.import_translations("fr-FR", exported)
        assert count == 2
