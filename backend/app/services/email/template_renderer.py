"""
PARWA Email Template Renderer — Day 5 (Email Deep + Email MCP Server)

Per-tenant email template rendering with Jinja2.  Supports built-in
templates (ticket_update, auto_reply, escalation_notice,
satisfaction_survey) and per-tenant custom template registration.

Building Codes:
- BC-001: Templates scoped by company_id (multi-tenant isolation)
- BC-008: Never crash — all exceptions caught, return error dicts
"""

from __future__ import annotations

import logging
from typing import Optional

from jinja2 import BaseLoader, Environment, FileSystemLoader, TemplateError

logger = logging.getLogger("parwa.email_template_renderer")

# ── Built-in Template Definitions ────────────────────────────────

BUILTIN_TEMPLATES: dict[str, str] = {
    "ticket_update": (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'></head>\n"
        "<body style='font-family:sans-serif;margin:0;padding:20px;"
        "background:#f4f6f9'>\n"
        "<div style='max-width:600px;margin:0 auto;background:#fff;"
        "border-radius:8px;padding:30px'>\n"
        "  <div style='background:{{ primary_color | default('#8b5cf6') }};"
        "padding:20px;border-radius:6px 6px 0 0;text-align:center'>\n"
        "    <h2 style='color:#fff;margin:0'>{{ company_name | default('PARWA') }}</h2>\n"
        "  </div>\n"
        "  <div style='padding:20px'>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      Hi {{ customer_name | default('there') }},</p>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      Your ticket <strong>#{{ ticket_id | default('') }}</strong> "
        "has been updated:</p>\n"
        "    <div style='background:#f9fafb;border-radius:6px;"
        "padding:16px;margin:16px 0'>\n"
        "      {{ update_message | default('No details provided.') }}\n"
        "    </div>\n"
        "    {% if ticket_url %}\n"
        "    <p style='text-align:center;margin:20px 0'>\n"
        "      <a href='{{ ticket_url }}' "
        "style='background:{{ primary_color | default('#8b5cf6') }};"
        "color:#fff;padding:12px 24px;border-radius:6px;"
        "text-decoration:none;font-weight:600'>View Ticket</a>\n"
        "    </p>\n"
        "    {% endif %}\n"
        "  </div>\n"
        "  <div style='border-top:1px solid #eee;padding:16px;"
        "text-align:center;font-size:12px;color:#999'>\n"
        "    <p>&copy; {{ company_name | default('PARWA') }}. "
        "All rights reserved.</p>\n"
        "  </div>\n"
        "</div>\n"
        "</body></html>"
    ),
    "auto_reply": (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'></head>\n"
        "<body style='font-family:sans-serif;margin:0;padding:20px;"
        "background:#f4f6f9'>\n"
        "<div style='max-width:600px;margin:0 auto;background:#fff;"
        "border-radius:8px;padding:30px'>\n"
        "  <div style='background:{{ primary_color | default('#8b5cf6') }};"
        "padding:20px;border-radius:6px 6px 0 0;text-align:center'>\n"
        "    <h2 style='color:#fff;margin:0'>{{ company_name | default('PARWA') }}</h2>\n"
        "  </div>\n"
        "  <div style='padding:20px'>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      Hi {{ customer_name | default('there') }},</p>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      Thank you for reaching out! We've received your message "
        "and our team will get back to you shortly.</p>\n"
        "    <div style='background:#f9fafb;border-radius:6px;"
        "padding:16px;margin:16px 0'>\n"
        "      <p style='margin:0;font-size:14px;color:#666'>\n"
        "        <strong>Ticket #{{ ticket_id | default('') }}</strong></p>\n"
        "      <p style='margin:8px 0 0;font-size:14px;color:#666'>\n"
        "        {{ subject | default('') }}</p>\n"
        "    </div>\n"
        "    {% if ai_response %}\n"
        "    <div style='background:#f0fdf4;border-radius:6px;"
        "padding:16px;margin:16px 0'>\n"
        "      {{ ai_response }}\n"
        "    </div>\n"
        "    {% endif %}\n"
        "    <p style='font-size:14px;color:#666'>\n"
        "      Reference: {{ ticket_id | default('N/A') }}</p>\n"
        "  </div>\n"
        "  <div style='border-top:1px solid #eee;padding:16px;"
        "text-align:center;font-size:12px;color:#999'>\n"
        "    <p>&copy; {{ company_name | default('PARWA') }}. "
        "All rights reserved.</p>\n"
        "  </div>\n"
        "</div>\n"
        "</body></html>"
    ),
    "escalation_notice": (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'></head>\n"
        "<body style='font-family:sans-serif;margin:0;padding:20px;"
        "background:#f4f6f9'>\n"
        "<div style='max-width:600px;margin:0 auto;background:#fff;"
        "border-radius:8px;padding:30px'>\n"
        "  <div style='background:#dc2626;padding:20px;"
        "border-radius:6px 6px 0 0;text-align:center'>\n"
        "    <h2 style='color:#fff;margin:0'>⚠ Escalation Notice</h2>\n"
        "  </div>\n"
        "  <div style='padding:20px'>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      Hi {{ agent_name | default('Agent') }},</p>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      Ticket <strong>#{{ ticket_id | default('') }}</strong> "
        "has been escalated to <strong>Level {{ escalation_level | default('2') }}</strong>.</p>\n"
        "    <div style='background:#fef2f2;border-radius:6px;"
        "padding:16px;margin:16px 0;border-left:4px solid #dc2626'>\n"
        "      <p style='margin:0;font-weight:600'>Reason:</p>\n"
        "      <p style='margin:8px 0 0'>{{ escalation_reason | default('Not specified') }}</p>\n"
        "    </div>\n"
        "    {% if ticket_url %}\n"
        "    <p style='text-align:center;margin:20px 0'>\n"
        "      <a href='{{ ticket_url }}' "
        "style='background:#dc2626;color:#fff;padding:12px 24px;"
        "border-radius:6px;text-decoration:none;font-weight:600'>"
        "View Ticket</a>\n"
        "    </p>\n"
        "    {% endif %}\n"
        "  </div>\n"
        "  <div style='border-top:1px solid #eee;padding:16px;"
        "text-align:center;font-size:12px;color:#999'>\n"
        "    <p>&copy; {{ company_name | default('PARWA') }}. "
        "All rights reserved.</p>\n"
        "  </div>\n"
        "</div>\n"
        "</body></html>"
    ),
    "satisfaction_survey": (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'></head>\n"
        "<body style='font-family:sans-serif;margin:0;padding:20px;"
        "background:#f4f6f9'>\n"
        "<div style='max-width:600px;margin:0 auto;background:#fff;"
        "border-radius:8px;padding:30px'>\n"
        "  <div style='background:{{ primary_color | default('#8b5cf6') }};"
        "padding:20px;border-radius:6px 6px 0 0;text-align:center'>\n"
        "    <h2 style='color:#fff;margin:0'>{{ company_name | default('PARWA') }}</h2>\n"
        "  </div>\n"
        "  <div style='padding:20px'>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      Hi {{ customer_name | default('there') }},</p>\n"
        "    <p style='font-size:16px;line-height:1.6'>\n"
        "      We'd love to hear about your experience with ticket "
        "<strong>#{{ ticket_id | default('') }}</strong>.</p>\n"
        "    <div style='text-align:center;margin:24px 0'>\n"
        "      <p style='font-size:14px;color:#666;margin-bottom:12px'>"
        "How would you rate our service?</p>\n"
        "      <div style='display:inline-block'>\n"
        "        {% for i in range(1, 6) %}\n"
        "        <a href='{{ survey_url | default('#') }}&rating={{ i }}' "
        "style='display:inline-block;width:48px;height:48px;"
        "line-height:48px;text-align:center;background:{{ primary_color | default('#8b5cf6') }};"
        "color:#fff;text-decoration:none;border-radius:50%;"
        "margin:0 4px;font-size:20px;font-weight:600'>{{ i }}</a>\n"
        "        {% endfor %}\n"
        "      </div>\n"
        "    </div>\n"
        "    <p style='font-size:14px;color:#666;text-align:center'>\n"
        "      1 = Very Dissatisfied &nbsp;&nbsp; 5 = Very Satisfied</p>\n"
        "  </div>\n"
        "  <div style='border-top:1px solid #eee;padding:16px;"
        "text-align:center;font-size:12px;color:#999'>\n"
        "    <p>&copy; {{ company_name | default('PARWA') }}. "
        "All rights reserved.</p>\n"
        "  </div>\n"
        "</div>\n"
        "</body></html>"
    ),
}


class _TenantTemplateLoader(BaseLoader):
    """Custom Jinja2 loader that resolves templates per-tenant.

    Resolution order:
    1. Per-tenant custom template (from the ``_custom_templates`` dict)
    2. Built-in template (from ``BUILTIN_TEMPLATES``)
    3. Raise TemplateNotFound

    BC-001: Templates are always scoped by company_id.
    """

    def __init__(
        self,
        custom_templates: dict[str, dict[str, str]],
    ) -> None:
        self._custom_templates = custom_templates

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str, callable]:
        """Load template source, checking tenant custom templates first.

        The template name is expected to be in the format
        ``company_id:template_name`` for tenant-scoped resolution.

        Args:
            environment: The Jinja2 environment.
            template: Template name, either ``company_id:name`` or
                plain ``name`` (for built-in lookup).

        Returns:
            Tuple of (source, filename, uptodate_callable).

        Raises:
            TemplateError: If template not found.
        """
        # Parse company_id:template_name format
        company_id: Optional[str] = None
        template_name = template

        if ":" in template:
            parts = template.split(":", 1)
            company_id = parts[0]
            template_name = parts[1]

        # Check tenant custom templates first
        if company_id:
            tenant_templates = self._custom_templates.get(company_id, {})
            if template_name in tenant_templates:
                source = tenant_templates[template_name]
                return source, f"{company_id}:{template_name}", lambda: False

        # Fall back to built-in templates
        if template_name in BUILTIN_TEMPLATES:
            source = BUILTIN_TEMPLATES[template_name]
            return source, f"builtin:{template_name}", lambda: False

        # Not found
        from jinja2 import TemplateNotFound

        raise TemplateNotFound(template_name)


class EmailTemplateRenderer:
    """Dynamic per-tenant email template rendering with Jinja2.

    Supports:
    - Built-in templates: ticket_update, auto_reply,
      escalation_notice, satisfaction_survey
    - Per-tenant custom template registration
    - Variable interpolation with ``{{ variable }}`` syntax
    - HTML-safe rendering with autoescaping

    BC-001: All template operations are scoped by company_id.
    """

    def __init__(self) -> None:
        self._custom_templates: dict[str, dict[str, str]] = {}
        self._tenant_branding: dict[str, dict[str, str]] = {}

        # Create Jinja2 environment with autoescaping
        self._env = Environment(
            loader=_TenantTemplateLoader(self._custom_templates),
            autoescape=True,
        )

    # ── Template Rendering ───────────────────────────────────────

    def render_template(
        self,
        template_name: str,
        variables: dict,
        company_id: str,
    ) -> dict:
        """Render an email template with variable interpolation.

        Resolves the template in the following order:
        1. Per-tenant custom template (if registered)
        2. Built-in template

        Automatically injects tenant branding variables
        (primary_color, logo_url, company_name) from the company's
        brand settings.

        Args:
            template_name: Name of the template (e.g. ``"ticket_update"``).
            variables: Dict of variables for ``{{ }}`` interpolation.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with keys:
            - status: ``"ok"`` or ``"error"``
            - rendered: Rendered HTML string
            - template_name: The resolved template name
            - is_custom: Whether a custom template was used
            - error: Error message if status is ``"error"``
        """
        try:
            # Inject tenant branding into variables
            branding = self._tenant_branding.get(company_id, {})
            merged_vars: dict = {**branding, **variables}

            # Determine if tenant has a custom template
            is_custom = (
                company_id in self._custom_templates
                and template_name in self._custom_templates[company_id]
            )

            # Build scoped template key for loader
            scoped_name = f"{company_id}:{template_name}"

            template = self._env.get_template(scoped_name)
            rendered = template.render(**merged_vars)

            return {
                "status": "ok",
                "rendered": rendered,
                "template_name": template_name,
                "is_custom": is_custom,
            }

        except TemplateError as exc:
            logger.warning(
                "email_template_render_failed",
                extra={
                    "company_id": company_id,
                    "template_name": template_name,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "rendered": "",
                "template_name": template_name,
                "is_custom": False,
                "error": f"Template render error: {str(exc)[:300]}",
            }

        except Exception as exc:
            logger.error(
                "email_template_render_unexpected_error",
                extra={
                    "company_id": company_id,
                    "template_name": template_name,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "rendered": "",
                "template_name": template_name,
                "is_custom": False,
                "error": str(exc)[:500],
            }

    # ── Template Registration ────────────────────────────────────

    def register_template(
        self,
        template_name: str,
        template_content: str,
        company_id: str,
    ) -> dict:
        """Register a per-tenant custom email template.

        The template content is validated as valid Jinja2 before
        being stored.  If a template with the same name already
        exists for this tenant, it is overwritten.

        BC-001: Templates are scoped by company_id.

        Args:
            template_name: Name for the template (must be non-empty).
            template_content: Jinja2 template content (HTML).
            company_id: Tenant company ID.

        Returns:
            Dict with keys:
            - status: ``"ok"`` or ``"error"``
            - template_name: The registered template name
            - is_update: Whether an existing template was updated
            - error: Error message if status is ``"error"``
        """
        try:
            if not template_name or not template_name.strip():
                return {
                    "status": "error",
                    "template_name": template_name,
                    "is_update": False,
                    "error": "template_name must be non-empty",
                }

            if not template_content or not template_content.strip():
                return {
                    "status": "error",
                    "template_name": template_name,
                    "is_update": False,
                    "error": "template_content must be non-empty",
                }

            # Validate template by attempting to parse it
            try:
                self._env.parse(template_content)
            except TemplateError as exc:
                return {
                    "status": "error",
                    "template_name": template_name,
                    "is_update": False,
                    "error": f"Invalid Jinja2 template: {str(exc)[:300]}",
                }

            # Check if this is an update
            is_update = (
                company_id in self._custom_templates
                and template_name in self._custom_templates[company_id]
            )

            # Store the custom template
            if company_id not in self._custom_templates:
                self._custom_templates[company_id] = {}

            self._custom_templates[company_id][template_name] = template_content

            logger.info(
                "email_template_registered",
                extra={
                    "company_id": company_id,
                    "template_name": template_name,
                    "is_update": is_update,
                },
            )

            return {
                "status": "ok",
                "template_name": template_name,
                "is_update": is_update,
            }

        except Exception as exc:
            logger.error(
                "email_template_register_failed",
                extra={
                    "company_id": company_id,
                    "template_name": template_name,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "template_name": template_name,
                "is_update": False,
                "error": str(exc)[:500],
            }

    # ── Template Listing ─────────────────────────────────────────

    def list_templates(self, company_id: str) -> dict:
        """List available email templates for a tenant.

        Returns both built-in templates and any per-tenant custom
        templates.  BC-001: Only returns templates accessible to
        the given company_id.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with keys:
            - status: ``"ok"``
            - builtin_templates: List of built-in template names
            - custom_templates: List of custom template names for
              this tenant
            - total: Total count of available templates
        """
        try:
            builtin = sorted(BUILTIN_TEMPLATES.keys())
            custom = sorted(
                self._custom_templates.get(company_id, {}).keys()
            )

            return {
                "status": "ok",
                "builtin_templates": builtin,
                "custom_templates": custom,
                "total": len(builtin) + len(custom),
            }

        except Exception as exc:
            logger.error(
                "email_template_list_failed",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "builtin_templates": [],
                "custom_templates": [],
                "total": 0,
                "error": str(exc)[:500],
            }

    # ── Branding Management ──────────────────────────────────────

    def set_tenant_branding(
        self,
        company_id: str,
        primary_color: Optional[str] = None,
        logo_url: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> dict:
        """Set branding variables for a tenant's email templates.

        These are automatically injected into every template render
        call for this tenant.

        BC-001: Branding scoped by company_id.

        Args:
            company_id: Tenant company ID.
            primary_color: Brand primary hex color (e.g. ``"#8b5cf6"``).
            logo_url: URL to the company logo image.
            company_name: Company display name.

        Returns:
            Dict with status and updated branding settings.
        """
        try:
            if company_id not in self._tenant_branding:
                self._tenant_branding[company_id] = {}

            branding = self._tenant_branding[company_id]

            if primary_color is not None:
                branding["primary_color"] = primary_color
            if logo_url is not None:
                branding["logo_url"] = logo_url
            if company_name is not None:
                branding["company_name"] = company_name

            return {
                "status": "ok",
                "branding": dict(branding),
            }

        except Exception as exc:
            logger.error(
                "email_template_branding_failed",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "branding": {},
                "error": str(exc)[:500],
            }

    def get_tenant_branding(self, company_id: str) -> dict:
        """Get current branding settings for a tenant.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with branding variables.
        """
        return {
            "status": "ok",
            "branding": dict(self._tenant_branding.get(company_id, {})),
        }
