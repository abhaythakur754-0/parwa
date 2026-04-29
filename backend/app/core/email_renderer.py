"""
PARWA Email Template Renderer (BC-006)

Renders Jinja2 email templates for transactional emails.
BC-006: All emails use templates (no hardcoded bodies).
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# Template directory
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "emails"

# Jinja2 environment (loaded once)
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def render_email_template(
    template_name: str,
    context: dict,
) -> str:
    """Render a Jinja2 email template with context.

    Args:
        template_name: Template filename
            (e.g. 'verification_email.html').
        context: Dict of variables for the template.

    Returns:
        Rendered HTML string.

    Raises:
        ValueError: If template not found.
    """
    try:
        template = _env.get_template(template_name)
        return template.render(**context)
    except Exception as exc:
        raise ValueError("Failed to render email template " f"'{template_name}': {exc}")
