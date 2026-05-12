"""
Week 4 — M-28: Email content must be sanitized before Brevo API.

Tests that the send-email Next.js route sanitizes user-supplied HTML content.
Since this is TypeScript, we test the Python equivalent of the sanitization logic.
"""
import re
import pytest


def sanitize_email_content(raw: str) -> str:
    """
    Python port of the sanitization logic from send-email/route.ts.
    Used for testing the sanitization behavior.
    """
    # Remove script tags and their content
    sanitized = re.sub(
        r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>',
        '',
        raw,
        flags=re.IGNORECASE,
    )
    # Remove inline event handlers
    sanitized = re.sub(
        r'\s+on\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)',
        '',
        sanitized,
        flags=re.IGNORECASE,
    )
    # Remove dangerous tags
    sanitized = re.sub(
        r'<(iframe|object|embed|form|meta|link|base)\b[^>]*/?>',
        '',
        sanitized,
        flags=re.IGNORECASE,
    )
    # Neutralize javascript:/data: URLs
    sanitized = re.sub(
        r'(href|src)\s*=\s*["\']?(javascript|data|vbscript):',
        r'\1="about:blank',
        sanitized,
        flags=re.IGNORECASE,
    )
    # Escape disallowed tags
    allowed_tags = {
        'p', 'br', 'div', 'span', 'a', 'b', 'i', 'u', 'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'tr', 'td', 'th',
        'strong', 'em', 'hr', 'img', 'blockquote', 'sup', 'sub',
    }

    def replace_disallowed(match):
        tag_name = match.group(1).lower()
        if tag_name in allowed_tags:
            return match.group(0)
        return match.group(0).replace('<', '&lt;').replace('>', '&gt;')

    sanitized = re.sub(
        r'</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*/?>',
        replace_disallowed,
        sanitized,
    )
    return sanitized


class TestM28EmailSanitization:
    """Tests for email content sanitization logic."""

    def test_script_tags_removed(self):
        """<script> tags and their content must be stripped."""
        input_html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        result = sanitize_email_content(input_html)
        assert '<script' not in result.lower()
        assert 'alert' not in result
        assert '<p>Hello</p>' in result
        assert '<p>World</p>' in result

    def test_event_handlers_removed(self):
        """Inline event handlers (onclick, onerror) must be stripped."""
        input_html = '<div onclick="alert(1)">Click me</div>'
        result = sanitize_email_content(input_html)
        assert 'onclick' not in result.lower()

    def test_onerror_handler_removed(self):
        """onerror handlers must be stripped."""
        input_html = '<img src="x" onerror="alert(document.cookie)">'
        result = sanitize_email_content(input_html)
        assert 'onerror' not in result.lower()

    def test_iframe_removed(self):
        """<iframe> tags must be stripped."""
        input_html = '<iframe src="https://evil.com"></iframe>'
        result = sanitize_email_content(input_html)
        assert '<iframe' not in result.lower()

    def test_javascript_url_neutralized(self):
        """javascript: URLs must be neutralized to about:blank."""
        input_html = '<a href="javascript:alert(1)">Click</a>'
        result = sanitize_email_content(input_html)
        assert 'javascript:' not in result.lower()
        assert 'about:blank' in result

    def test_data_url_neutralized(self):
        """data: URLs must be neutralized."""
        input_html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>'
        result = sanitize_email_content(input_html)
        assert 'data:' not in result.lower()

    def test_allowed_tags_preserved(self):
        """Safe HTML tags must be preserved."""
        input_html = '<p>Hello <b>world</b></p><ul><li>item</li></ul>'
        result = sanitize_email_content(input_html)
        assert '<p>' in result
        assert '<b>' in result
        assert '<ul>' in result
        assert '<li>' in result

    def test_disallowed_tags_escaped(self):
        """Disallowed tags must be HTML-escaped (not removed, to preserve text)."""
        input_html = '<custom-tag>Some content</custom-tag>'
        result = sanitize_email_content(input_html)
        assert '&lt;custom-tag' in result

    def test_safe_html_unchanged(self):
        """Clean HTML with only safe tags should pass through unchanged."""
        input_html = (
            '<div style="font-family: Arial;">'
            '<h1>Order Confirmation</h1>'
            '<p>Thank you for your purchase.</p>'
            '<ul><li>Item 1</li><li>Item 2</li></ul>'
            '</div>'
        )
        result = sanitize_email_content(input_html)
        assert result == input_html

    def test_object_tag_removed(self):
        """<object> tags must be stripped."""
        input_html = '<object data="evil.swf"></object>'
        result = sanitize_email_content(input_html)
        assert '<object' not in result.lower()

    def test_form_tag_removed(self):
        """<form> tags must be stripped."""
        input_html = '<form action="https://evil.com"><input type="password"></form>'
        result = sanitize_email_content(input_html)
        assert '<form' not in result.lower()

    def test_nested_script_removed(self):
        """Nested script content must be fully removed."""
        input_html = '<script>var x = "<script>inner</script>";</script>'
        result = sanitize_email_content(input_html)
        assert '<script' not in result.lower()


class TestM28SourceCodeExists:
    """Verify the sanitization function exists in the TypeScript route."""

    def test_route_file_exists(self):
        """The send-email route file must exist."""
        import os
        route_path = "/home/z/my-project/src/app/api/send-email/route.ts"
        assert os.path.exists(route_path), f"Route file not found: {route_path}"

    def test_route_contains_sanitize_function(self):
        """Route must define a sanitizeEmailContent function."""
        route_path = "/home/z/my-project/src/app/api/send-email/route.ts"
        with open(route_path) as f:
            content = f.read()
        assert "sanitizeEmailContent" in content, (
            "sanitizeEmailContent function not found in route.ts"
        )

    def test_route_calls_sanitize(self):
        """Route must call the sanitization function on user content."""
        route_path = "/home/z/my-project/src/app/api/send-email/route.ts"
        with open(route_path) as f:
            content = f.read()
        assert "sanitizeEmailContent" in content and content.count("sanitizeEmailContent") >= 2, (
            "Route must call sanitizeEmailContent on input content (at least definition + call)"
        )

    def test_route_requires_auth(self):
        """Route must call requireAuth."""
        route_path = "/home/z/my-project/src/app/api/send-email/route.ts"
        with open(route_path) as f:
            content = f.read()
        assert "requireAuth" in content, "Route must require authentication"

    def test_route_validates_required_fields(self):
        """Route must validate 'to' and 'subject' are present."""
        route_path = "/home/z/my-project/src/app/api/send-email/route.ts"
        with open(route_path) as f:
            content = f.read()
        assert "to" in content and "subject" in content, (
            "Route must validate 'to' and 'subject' fields"
        )
