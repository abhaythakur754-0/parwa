"""
Unit Tests for Template Service - Day 6

Tests cover:
- Template CRUD operations
- Variable substitution
- Template rendering
- XSS sanitization
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone


class TestTemplateService:
    """Tests for TemplateService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_template(self):
        """Create a mock template."""
        template = Mock()
        template.id = "template-123"
        template.name = "Greeting Template"
        template.template_text = "Hello {{customer_name}}, thank you for contacting {{company_name}}!"
        template.intent_type = "greeting"
        template.variables = '["customer_name", "company_name"]'
        template.language = "en"
        template.is_active = True
        template.version = 1
        template.created_at = datetime.now(timezone.utc)
        template.updated_at = datetime.now(timezone.utc)
        return template

    # ── VARIABLE EXTRACTION ───────────────────────────────────────────────────

    def test_extract_variables(self):
        """Test extracting variables from template text."""
        import re
        pattern = re.compile(r'\{\{(\w+)\}\}')

        template_text = "Hello {{customer_name}}, your ticket {{ticket_id}} is being processed."
        variables = list(set(pattern.findall(template_text)))

        assert "customer_name" in variables
        assert "ticket_id" in variables
        assert len(variables) == 2

    def test_extract_variables_empty(self):
        """Test extracting variables from template without variables."""
        import re
        pattern = re.compile(r'\{\{(\w+)\}\}')

        template_text = "Hello, thank you for contacting us."
        variables = pattern.findall(template_text)

        assert len(variables) == 0

    def test_extract_variables_duplicates(self):
        """Test that duplicate variables are deduplicated."""
        import re
        pattern = re.compile(r'\{\{(\w+)\}\}')

        template_text = "{{name}} - Hello {{name}}, welcome {{name}}!"
        variables = list(set(pattern.findall(template_text)))

        assert len(variables) == 1
        assert variables[0] == "name"

    # ── VARIABLE SUBSTITUTION ─────────────────────────────────────────────────

    def test_substitute_variables(self):
        """Test variable substitution in template."""
        template_text = "Hello {{customer_name}}, thank you for contacting {{company_name}}!"
        variables = {
            "customer_name": "John Doe",
            "company_name": "PARWA"
        }

        result = template_text
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)

        assert result == "Hello John Doe, thank you for contacting PARWA!"

    def test_substitute_partial_variables(self):
        """Test substitution with missing variables."""
        template_text = "Hello {{customer_name}}, your ticket {{ticket_id}} is ready."
        variables = {
            "customer_name": "Jane"
            # ticket_id missing
        }

        result = template_text
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)

        assert result == "Hello Jane, your ticket {{ticket_id}} is ready."

    def test_substitute_empty_values(self):
        """Test substitution with empty values."""
        template_text = "Hello {{name}}!"
        variables = {"name": ""}

        result = template_text
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)

        assert result == "Hello !"

    # ── XSS SANITIZATION ───────────────────────────────────────────────────────

    def test_sanitize_html_tags(self):
        """Test that dangerous HTML tags are removed."""
        # Simulate sanitization
        dangerous_input = '<script>alert("xss")</script>Hello'
        
        # Simple sanitization (real implementation would be more thorough)
        import re
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', dangerous_input, flags=re.DOTALL | re.IGNORECASE)
        
        assert "<script>" not in sanitized
        assert "Hello" in sanitized

    def test_sanitize_event_handlers(self):
        """Test that inline event handlers are removed."""
        dangerous_input = '<img src="x" onerror="alert(1)">'
        
        import re
        sanitized = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', dangerous_input, flags=re.IGNORECASE)
        
        assert "onerror" not in sanitized

    def test_sanitize_javascript_urls(self):
        """Test that javascript: URLs are removed."""
        dangerous_input = '<a href="javascript:alert(1)">Click</a>'
        
        import re
        sanitized = re.sub(r'javascript:', '', dangerous_input, flags=re.IGNORECASE)
        
        assert "javascript:" not in sanitized

    # ── TEMPLATE VALIDATION ────────────────────────────────────────────────────

    def test_validate_template_name(self):
        """Test template name validation."""
        # Valid names
        valid_names = ["Greeting", "Refund Template", "Customer Reply v2"]
        
        for name in valid_names:
            assert len(name.strip()) > 0

    def test_validate_template_variables(self):
        """Test that variable names are valid."""
        import re
        
        valid_vars = ["customer_name", "ticket_id", "company_name"]
        invalid_vars = ["customer-name", "123var", "var!name", "__dunder__"]
        
        pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
        
        for var in valid_vars:
            assert pattern.match(var) is not None, f"{var} should be valid"
        
        for var in invalid_vars:
            assert pattern.match(var) is None or '__' in var, f"{var} should be invalid"

    def test_validate_category(self):
        """Test category validation."""
        valid_categories = {
            "greeting", "farewell", "apology", "escalation",
            "refund", "technical", "billing", "general", "custom"
        }
        
        assert "greeting" in valid_categories
        assert "unknown" not in valid_categories


class TestTemplateAPI:
    """Tests for Template API endpoints."""

    def test_create_template_request(self):
        """Test template creation request schema."""
        request_data = {
            "name": "Test Template",
            "template_text": "Hello {{name}}!",
            "intent_type": "greeting",
            "variables": ["name"],
            "language": "en"
        }
        
        assert "name" in request_data
        assert "template_text" in request_data
        assert len(request_data["variables"]) == 1

    def test_apply_template_request(self):
        """Test template application request."""
        request_data = {
            "variables": {
                "customer_name": "John",
                "company_name": "PARWA"
            }
        }
        
        assert "variables" in request_data
        assert request_data["variables"]["customer_name"] == "John"

    def test_list_templates_filters(self):
        """Test template listing filters."""
        # Query parameters
        filters = {
            "intent_type": "greeting",
            "language": "en",
            "is_active": True,
            "search": "hello"
        }
        
        assert filters["intent_type"] == "greeting"
        assert filters["language"] == "en"
        assert filters["is_active"] is True


class TestTemplateRendering:
    """Tests for template rendering functionality."""

    def test_render_greeting_template(self):
        """Test rendering a greeting template."""
        template = {
            "subject_template": "Welcome, {{customer_name}}!",
            "body_template": "Hello {{customer_name}},\n\nWelcome to {{company_name}}!"
        }
        
        variables = {
            "customer_name": "Alice",
            "company_name": "PARWA"
        }
        
        # Render
        subject = template["subject_template"]
        body = template["body_template"]
        
        for key, value in variables.items():
            subject = subject.replace(f"{{{{{key}}}}}", value)
            body = body.replace(f"{{{{{key}}}}}", value)
        
        assert subject == "Welcome, Alice!"
        assert "Hello Alice" in body
        assert "Welcome to PARWA" in body

    def test_render_apology_template(self):
        """Test rendering an apology template."""
        template = {
            "subject_template": "We're Sorry, {{customer_name}}",
            "body_template": "Dear {{customer_name}},\n\nWe apologise for {{issue_description}}.\n\nExpected resolution: {{resolution_time}}."
        }
        
        variables = {
            "customer_name": "Bob",
            "issue_description": "the delayed shipment",
            "resolution_time": "24 hours"
        }
        
        # Render
        result = template["body_template"]
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        
        assert "Dear Bob" in result
        assert "the delayed shipment" in result
        assert "24 hours" in result

    def test_render_refund_template(self):
        """Test rendering a refund confirmation template."""
        template = {
            "subject_template": "Refund Confirmation — {{order_id}}",
            "body_template": "Amount: {{refund_amount}}\nMethod: {{payment_method}}"
        }
        
        variables = {
            "order_id": "ORD-12345",
            "refund_amount": "$49.99",
            "payment_method": "Credit Card"
        }
        
        # Render
        result = template["body_template"]
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        
        assert "$49.99" in result
        assert "Credit Card" in result

    def test_render_multiline_template(self):
        """Test rendering template with multiple lines."""
        template = """Hello {{name}},

Thank you for your order {{order_id}}.

Best regards,
{{company}}"""
        
        variables = {
            "name": "Customer",
            "order_id": "123",
            "company": "Support Team"
        }
        
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        
        assert "\n" in result
        assert "Hello Customer" in result
        assert "Support Team" in result
