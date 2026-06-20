"""Tests for email templates existence and structure."""

import os


TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "backend", "app", "templates", "emails",
)

ALL_TEMPLATES = [
    "base.html",
    "verification_email.html",
    "password_reset_email.html",
    "welcome_email.html",
    "mfa_enabled.html",
    "session_revoked.html",
    "api_key_created.html",
    "approval_notification.html",
    "overage_notification.html",
]

CHILD_TEMPLATES = [
    "verification_email.html",
    "password_reset_email.html",
    "welcome_email.html",
    "mfa_enabled.html",
    "session_revoked.html",
    "api_key_created.html",
    "approval_notification.html",
    "overage_notification.html",
]


def _read_template(fname):
    path = os.path.join(TEMPLATES_DIR, fname)
    with open(path) as f:
        return f.read()


class TestTemplateExistence:
    def test_base_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "base.html")
        assert os.path.exists(path)

    def test_verification_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "verification_email.html")
        assert os.path.exists(path)

    def test_password_reset_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "password_reset_email.html")
        assert os.path.exists(path)

    def test_welcome_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "welcome_email.html")
        assert os.path.exists(path)

    def test_mfa_enabled_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "mfa_enabled.html")
        assert os.path.exists(path)

    def test_session_revoked_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "session_revoked.html")
        assert os.path.exists(path)

    def test_api_key_created_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "api_key_created.html")
        assert os.path.exists(path)

    def test_approval_notification_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "approval_notification.html")
        assert os.path.exists(path)

    def test_overage_notification_template_exists(self):
        path = os.path.join(TEMPLATES_DIR, "overage_notification.html")
        assert os.path.exists(path)

    def test_all_8_child_templates_exist(self):
        for fname in CHILD_TEMPLATES:
            path = os.path.join(TEMPLATES_DIR, fname)
            assert os.path.exists(path), f"Missing: {fname}"


class TestTemplateStructure:
    def test_base_template_has_block_body(self):
        content = _read_template("base.html")
        assert "{% block body %}" in content

    def test_base_template_has_extends_in_children(self):
        for fname in CHILD_TEMPLATES:
            content = _read_template(fname)
            assert '{% extends "base.html" %}' in content, f"{fname} doesn't extend base.html"

    def test_all_children_have_body_block(self):
        for fname in CHILD_TEMPLATES:
            content = _read_template(fname)
            assert "{% block body %}" in content, f"{fname} missing body block"

    def test_base_template_has_parwa_header(self):
        content = _read_template("base.html")
        assert "PARWA" in content

    def test_base_template_has_footer(self):
        content = _read_template("base.html")
        assert "footer" in content.lower()

    def test_base_template_has_responsive_viewport(self):
        content = _read_template("base.html")
        assert "viewport" in content

    def test_base_template_has_doctype(self):
        content = _read_template("base.html")
        assert "<!DOCTYPE html>" in content


class TestTemplateJinja2Usage:
    def test_verification_email_uses_variables(self):
        content = _read_template("verification_email.html")
        assert "{{ user_name }}" in content
        assert "{{ verification_url }}" in content

    def test_password_reset_uses_variables(self):
        content = _read_template("password_reset_email.html")
        assert "{{ user_name }}" in content
        assert "{{ reset_url }}" in content

    def test_welcome_email_uses_variables(self):
        content = _read_template("welcome_email.html")
        assert "{{ user_name }}" in content
        assert "{{ dashboard_url }}" in content

    def test_mfa_enabled_uses_variables(self):
        content = _read_template("mfa_enabled.html")
        assert "{{ user_name }}" in content
        assert "{{ ip_address }}" in content
        assert "{{ timestamp }}" in content

    def test_session_revoked_uses_variables(self):
        content = _read_template("session_revoked.html")
        assert "{{ user_name }}" in content
        assert "{{ device_info }}" in content

    def test_api_key_created_uses_variables(self):
        content = _read_template("api_key_created.html")
        assert "{{ user_name }}" in content
        assert "{{ key_name }}" in content
        assert "{{ api_key }}" in content

    def test_approval_notification_uses_variables(self):
        content = _read_template("approval_notification.html")
        assert "{{ user_name }}" in content
        assert "{{ approval_id }}" in content
        assert "{{ action_type }}" in content

    def test_overage_notification_uses_variables(self):
        content = _read_template("overage_notification.html")
        assert "{{ user_name }}" in content
        assert "{{ plan_name }}" in content
        assert "{{ total_overage_amount }}" in content


class TestTemplateSafety:
    def test_no_script_tags_in_any_template(self):
        for fname in ALL_TEMPLATES:
            content = _read_template(fname)
            assert "<script" not in content.lower(), f"{fname} contains script tag"

    def test_no_onclick_in_any_template(self):
        for fname in ALL_TEMPLATES:
            content = _read_template(fname)
            assert "onclick" not in content.lower(), f"{fname} contains onclick"

    def test_no_inline_javascript_in_any_template(self):
        for fname in ALL_TEMPLATES:
            content = _read_template(fname)
            assert "javascript:" not in content.lower(), f"{fname} contains javascript:"

    def test_no_dangerously_set_inner_html(self):
        for fname in ALL_TEMPLATES:
            content = _read_template(fname)
            assert "dangerouslySetInnerHTML" not in content

    def test_no_v_html_in_any_template(self):
        for fname in ALL_TEMPLATES:
            content = _read_template(fname)
            assert "v-html" not in content


class TestTemplateBranding:
    def test_base_template_has_gradient_header(self):
        content = _read_template("base.html")
        assert "linear-gradient" in content

    def test_base_template_has_button_style(self):
        content = _read_template("base.html")
        assert ".btn" in content

    def test_base_template_has_container_style(self):
        content = _read_template("base.html")
        assert ".container" in content

    def test_welcome_email_has_cta_button(self):
        content = _read_template("welcome_email.html")
        assert 'class="btn"' in content

    def test_api_key_template_has_manage_button(self):
        content = _read_template("api_key_created.html")
        assert 'class="btn"' in content

    def test_approval_template_has_approve_button(self):
        content = _read_template("approval_notification.html")
        assert 'class="btn"' in content

    def test_overage_template_has_billing_button(self):
        content = _read_template("overage_notification.html")
        assert 'class="btn"' in content
