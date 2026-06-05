"""
PARWA Email Services Package — Day 5 (Email Deep + Email MCP Server)

Sub-modules:
- email_parser: HTML parsing, thread tracking, attachment extraction,
  signature detection, quoted-reply stripping
- email_to_ticket: Inbound email → Ticket/TicketMessage conversion
- template_renderer: Per-tenant Jinja2 email template rendering

Building Codes:
- BC-001: All operations scoped by company_id
- BC-008: Never crash — all exceptions caught, return error dicts
"""

from app.services.email.email_parser import EmailParser
from app.services.email.email_to_ticket import EmailToTicketConverter
from app.services.email.template_renderer import EmailTemplateRenderer

__all__ = [
    "EmailParser",
    "EmailToTicketConverter",
    "EmailTemplateRenderer",
]
