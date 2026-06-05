"""
SMS Templates & TCPA Compliance — Day 6 SMS Deep Services

Provides two classes:

1. SMSTemplateManager: Per-tenant SMS template management with Jinja2
   rendering. Templates use {{ variable }} syntax. Built-in templates
   for common workflows (ticket_update, auto_reply, opt_out_confirmation,
   satisfaction_survey).

2. TCPAManager: TCPA compliance engine with consent tracking, quiet
   hours enforcement, and pre-send compliance checks.

Building Codes:
- BC-001: Multi-tenant isolation (all operations scoped to company_id)
- BC-008: Never crash — wrap all external calls in try/except
- BC-010: TCPA compliance (opt-out/STOP keywords, consent tracking)
- BC-012: Structured error responses
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from jinja2 import BaseLoader, Environment, TemplateSyntaxError
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from database.models.sms_channel import (
    SMSChannelConfig,
    SMSConversation,
    SMSMessage,
)

logger = logging.getLogger("parwa.sms.templates")

# ── Jinja2 Environment (autoescaping disabled for SMS) ────────

_jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=False,  # SMS is plain text — no HTML escaping needed
)

# ── Template Variable Pattern ─────────────────────────────────

_TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# ── SMS Segment Calculation ───────────────────────────────────

_GSM_CHAR_LIMIT = 160  # GSM-7 single segment limit
_UNICODE_CHAR_LIMIT = 70  # Unicode single segment limit

# ── Built-in Template Definitions ─────────────────────────────

BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ticket_update": {
        "body_template": (
            "Hi {{ customer_name }}, your ticket #{{ ticket_id }} "
            "has been updated: {{ update_message }}. "
            "Status: {{ ticket_status }}. Reply STOP to opt out."
        ),
        "variables": [
            "customer_name",
            "ticket_id",
            "update_message",
            "ticket_status",
        ],
    },
    "auto_reply": {
        "body_template": (
            "Thanks for reaching out, {{ customer_name }}! "
            "We've received your message and an agent will respond "
            "shortly. Your reference: #{{ ticket_id }}. "
            "Reply STOP to opt out."
        ),
        "variables": ["customer_name", "ticket_id"],
    },
    "opt_out_confirmation": {
        "body_template": (
            "You have been unsubscribed from SMS messages from "
            "{{ company_name }}. You will receive no further messages. "
            "Reply START to resubscribe."
        ),
        "variables": ["company_name"],
    },
    "satisfaction_survey": {
        "body_template": (
            "Hi {{ customer_name }}, how was your experience with "
            "ticket #{{ ticket_id }}? Reply 1-5 (5=great). "
            "Reply STOP to opt out."
        ),
        "variables": ["customer_name", "ticket_id"],
    },
}

# ── Quiet Hours Defaults ──────────────────────────────────────

DEFAULT_QUIET_HOURS_START = time(21, 0)  # 9:00 PM
DEFAULT_QUIET_HOURS_END = time(9, 0)  # 9:00 AM


# ═══════════════════════════════════════════════════════════════
# In-Memory Template Store (per company_id)
# ═══════════════════════════════════════════════════════════════

# In production this would be a database table. For Day 6 we use
# an in-memory dict keyed by (company_id, template_id).
_template_store: Dict[str, Dict[str, Dict[str, Any]]] = {}

# In-memory consent records store keyed by (company_id, phone_number)
_consent_store: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

# In-memory counter for quiet hours violations blocked
_quiet_hours_blocked: Dict[str, int] = {}


class SMSTemplateManager:
    """Per-tenant SMS template management with Jinja2 rendering.

    Templates use {{ variable }} syntax and are scoped by company_id
    (BC-001). Built-in templates are automatically available for all
    tenants.
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # Template CRUD
    # ═══════════════════════════════════════════════════════════

    def create_template(
        self,
        template_name: str,
        body_template: str,
        variables: List[str],
        company_id: str,
    ) -> dict:
        """Create a per-tenant SMS template.

        Args:
            template_name: Human-readable template name.
            body_template: Template body using {{ variable }} syntax.
            variables: List of expected variable names.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with template_id, template_name.
        """
        try:
            # Validate template syntax via Jinja2
            try:
                _jinja_env.from_string(body_template)
            except TemplateSyntaxError as exc:
                return {
                    "status": "error",
                    "error": f"Invalid template syntax: {str(exc)[:200]}",
                }

            # Validate variable names are alphanumeric/underscore
            for var in variables:
                if not re.match(r"^\w+$", var):
                    return {
                        "status": "error",
                        "error": f"Invalid variable name: '{var}'. Use alphanumeric and underscores only.",
                    }

            # Verify variables in template match declared variables
            template_vars = set(_TEMPLATE_VAR_PATTERN.findall(body_template))
            declared_vars = set(variables)
            if template_vars != declared_vars:
                missing = template_vars - declared_vars
                extra = declared_vars - template_vars
                parts = []
                if missing:
                    parts.append(f"Used but not declared: {', '.join(sorted(missing))}")
                if extra:
                    parts.append(f"Declared but not used: {', '.join(sorted(extra))}")
                return {
                    "status": "error",
                    "error": f"Variable mismatch. {'; '.join(parts)}",
                }

            # Generate template ID
            template_id = str(uuid.uuid4())

            # Store template
            if company_id not in _template_store:
                _template_store[company_id] = {}

            template_record = {
                "id": template_id,
                "template_name": template_name,
                "body_template": body_template,
                "variables": variables,
                "company_id": company_id,
                "is_builtin": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _template_store[company_id][template_id] = template_record

            # Also index by name for lookup
            _template_store[company_id][f"name:{template_name}"] = template_record

            logger.info(
                "sms_template_created",
                extra={
                    "company_id": company_id,
                    "template_id": template_id,
                    "template_name": template_name,
                },
            )

            return {
                "status": "created",
                "template_id": template_id,
                "template_name": template_name,
            }

        except Exception as exc:
            logger.exception(
                "sms_template_create_error",
                extra={
                    "company_id": company_id,
                    "template_name": template_name,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to create template: {str(exc)[:200]}",
            }

    def render_template(
        self,
        template_name: str,
        variable_values: Dict[str, str],
        company_id: str,
    ) -> dict:
        """Render template with variable interpolation.

        Args:
            template_name: Name of the template to render.
            variable_values: Dict mapping variable names to values.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with rendered_body, char_count, num_segments.
        """
        try:
            # Find template (custom first, then built-in)
            template = self._find_template(company_id, template_name)

            if not template:
                return {
                    "status": "error",
                    "error": f"Template '{template_name}' not found",
                }

            body_template = template["body_template"]
            variables = template.get("variables", [])

            # Check for missing variables
            missing_vars = []
            for var in variables:
                if var not in variable_values:
                    missing_vars.append(var)

            if missing_vars:
                return {
                    "status": "error",
                    "error": f"Missing variables: {', '.join(missing_vars)}",
                }

            # Render using Jinja2
            try:
                jinja_template = _jinja_env.from_string(body_template)
                rendered_body = jinja_template.render(**variable_values)
            except TemplateSyntaxError as exc:
                return {
                    "status": "error",
                    "error": f"Template rendering error: {str(exc)[:200]}",
                }
            except Exception as exc:
                return {
                    "status": "error",
                    "error": f"Template render failed: {str(exc)[:200]}",
                }

            # Calculate SMS metrics
            char_count = len(rendered_body)
            num_segments = self._calculate_segments(rendered_body)

            return {
                "status": "rendered",
                "rendered_body": rendered_body,
                "char_count": char_count,
                "num_segments": num_segments,
                "template_name": template_name,
            }

        except Exception as exc:
            logger.exception(
                "sms_template_render_error",
                extra={
                    "company_id": company_id,
                    "template_name": template_name,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to render template: {str(exc)[:200]}",
            }

    def update_template(
        self,
        template_id: str,
        updates: dict,
        company_id: str,
    ) -> dict:
        """Update template content/variables.

        Args:
            template_id: Template UUID.
            updates: Dict with fields to update (body_template, variables,
                     template_name).
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with status and updated template details.
        """
        try:
            company_templates = _template_store.get(company_id, {})
            template = company_templates.get(template_id)

            if not template:
                return {
                    "status": "error",
                    "error": "Template not found",
                }

            if template.get("is_builtin"):
                return {
                    "status": "error",
                    "error": "Cannot modify built-in templates",
                }

            # Validate new body_template if provided
            new_body = updates.get("body_template", template["body_template"])
            new_variables = updates.get("variables", template["variables"])
            new_name = updates.get("template_name", template["template_name"])

            # Validate Jinja2 syntax
            try:
                _jinja_env.from_string(new_body)
            except TemplateSyntaxError as exc:
                return {
                    "status": "error",
                    "error": f"Invalid template syntax: {str(exc)[:200]}",
                }

            # Validate variable alignment
            template_vars = set(_TEMPLATE_VAR_PATTERN.findall(new_body))
            declared_vars = set(new_variables)
            if template_vars != declared_vars:
                missing = template_vars - declared_vars
                extra = declared_vars - template_vars
                parts = []
                if missing:
                    parts.append(f"Used but not declared: {', '.join(sorted(missing))}")
                if extra:
                    parts.append(f"Declared but not used: {', '.join(sorted(extra))}")
                return {
                    "status": "error",
                    "error": f"Variable mismatch. {'; '.join(parts)}",
                }

            # Remove old name index
            old_name = template["template_name"]
            company_templates.pop(f"name:{old_name}", None)

            # Apply updates
            template["body_template"] = new_body
            template["variables"] = new_variables
            template["template_name"] = new_name
            template["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Update name index
            company_templates[f"name:{new_name}"] = template

            logger.info(
                "sms_template_updated",
                extra={
                    "company_id": company_id,
                    "template_id": template_id,
                },
            )

            return {
                "status": "updated",
                "template_id": template_id,
                "template_name": new_name,
                "variables": new_variables,
            }

        except Exception as exc:
            logger.exception(
                "sms_template_update_error",
                extra={
                    "company_id": company_id,
                    "template_id": template_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to update template: {str(exc)[:200]}",
            }

    def delete_template(
        self,
        template_id: str,
        company_id: str,
    ) -> dict:
        """Delete a custom template.

        Built-in templates cannot be deleted.

        Args:
            template_id: Template UUID.
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with status.
        """
        try:
            company_templates = _template_store.get(company_id, {})
            template = company_templates.get(template_id)

            if not template:
                return {
                    "status": "error",
                    "error": "Template not found",
                }

            if template.get("is_builtin"):
                return {
                    "status": "error",
                    "error": "Cannot delete built-in templates",
                }

            # Remove template and name index
            name = template["template_name"]
            company_templates.pop(template_id, None)
            company_templates.pop(f"name:{name}", None)

            logger.info(
                "sms_template_deleted",
                extra={
                    "company_id": company_id,
                    "template_id": template_id,
                    "template_name": name,
                },
            )

            return {"status": "deleted"}

        except Exception as exc:
            logger.exception(
                "sms_template_delete_error",
                extra={
                    "company_id": company_id,
                    "template_id": template_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to delete template: {str(exc)[:200]}",
            }

    def list_templates(
        self,
        company_id: str,
    ) -> dict:
        """List all templates for a tenant.

        Includes both built-in and custom templates.

        Args:
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with templates list.
        """
        try:
            templates = []

            # Add built-in templates
            for name, tpl_def in BUILTIN_TEMPLATES.items():
                templates.append({
                    "id": f"builtin:{name}",
                    "template_name": name,
                    "body_template": tpl_def["body_template"],
                    "variables": tpl_def["variables"],
                    "is_builtin": True,
                    "company_id": company_id,
                })

            # Add custom templates
            company_templates = _template_store.get(company_id, {})
            for key, tpl in company_templates.items():
                if not key.startswith("name:"):
                    templates.append(tpl.copy())

            return {
                "status": "success",
                "templates": templates,
                "total": len(templates),
            }

        except Exception as exc:
            logger.exception(
                "sms_template_list_error",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to list templates: {str(exc)[:200]}",
            }

    def get_template(
        self,
        template_id: str,
        company_id: str,
    ) -> dict:
        """Get template by ID.

        Args:
            template_id: Template UUID or "builtin:{name}".
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with template details.
        """
        try:
            # Check built-in
            if template_id.startswith("builtin:"):
                name = template_id[len("builtin:"):]
                if name in BUILTIN_TEMPLATES:
                    tpl = BUILTIN_TEMPLATES[name]
                    return {
                        "status": "success",
                        "template": {
                            "id": template_id,
                            "template_name": name,
                            "body_template": tpl["body_template"],
                            "variables": tpl["variables"],
                            "is_builtin": True,
                            "company_id": company_id,
                        },
                    }

            # Check custom templates
            company_templates = _template_store.get(company_id, {})
            template = company_templates.get(template_id)

            if not template:
                return {
                    "status": "error",
                    "error": "Template not found",
                }

            return {
                "status": "success",
                "template": template.copy(),
            }

        except Exception as exc:
            logger.exception(
                "sms_template_get_error",
                extra={
                    "company_id": company_id,
                    "template_id": template_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to get template: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Private Methods
    # ═══════════════════════════════════════════════════════════

    def _find_template(
        self,
        company_id: str,
        template_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Find a template by name, checking custom then built-in.

        Args:
            company_id: Tenant company ID.
            template_name: Template name to look up.

        Returns:
            Template dict if found, None otherwise.
        """
        # Check custom templates first
        company_templates = _template_store.get(company_id, {})
        by_name = company_templates.get(f"name:{template_name}")
        if by_name:
            return by_name

        # Fall back to built-in
        if template_name in BUILTIN_TEMPLATES:
            return {
                "id": f"builtin:{template_name}",
                "template_name": template_name,
                "body_template": BUILTIN_TEMPLATES[template_name]["body_template"],
                "variables": BUILTIN_TEMPLATES[template_name]["variables"],
                "is_builtin": True,
                "company_id": company_id,
            }

        return None

    def _calculate_segments(self, text: str) -> int:
        """Calculate the number of SMS segments for a message.

        Uses a simplified heuristic: if the text contains characters
        outside the GSM-7 alphabet, use Unicode segment limits.

        Args:
            text: Message text to calculate segments for.

        Returns:
            Number of SMS segments (minimum 1).
        """
        # Check if text contains non-GSM-7 characters
        if self._is_gsm7(text):
            char_limit = _GSM_CHAR_LIMIT
        else:
            char_limit = _UNICODE_CHAR_LIMIT

        if len(text) == 0:
            return 1

        return max(1, (len(text) + char_limit - 1) // char_limit)

    @staticmethod
    def _is_gsm7(text: str) -> bool:
        """Check if text can be encoded in GSM-7 basic character set.

        Args:
            text: Text to check.

        Returns:
            True if all characters are in GSM-7 basic set.
        """
        gsm7_chars = set(
            "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ"
            " !\"#¤%&'()*+,-./0123456789:;<=>?"
            "¡ABCDEFGHIJKLMNOQRSTUVWXYZÄÖÑÜ§¿"
            "abcdefghijklmnoqrstuvwxyzäöñüà"
            "^{}\\[~]|€"
        )
        return all(c in gsm7_chars for c in text)


class TCPAManager:
    """TCPA compliance engine for SMS communications.

    Provides consent tracking, quiet hours enforcement, and
    pre-send compliance checks. All operations are scoped by
    company_id (BC-001) and never crash (BC-008).
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # Consent Management
    # ═══════════════════════════════════════════════════════════

    def check_consent(
        self,
        company_id: str,
        phone_number: str,
    ) -> dict:
        """Check if a phone number has opted in.

        Checks both in-memory consent records and the SMSConversation
        table (if db session is available) for opt-out status.

        Args:
            company_id: Tenant company ID (BC-001).
            phone_number: Phone number to check.

        Returns:
            Dict with is_opted_in, consent_date, consent_source.
        """
        try:
            # Check in-memory consent store
            company_consents = _consent_store.get(company_id, {})
            records = company_consents.get(phone_number, [])

            # Find the most recent opt-in record
            opt_in_record = None
            opt_out_record = None
            for record in reversed(records):
                if record.get("consent_type") in ("explicit", "implicit", "manual"):
                    if record.get("action") == "opt_in" and opt_in_record is None:
                        opt_in_record = record
                    elif record.get("action") == "opt_out" and opt_out_record is None:
                        opt_out_record = record

            # Also check SMSConversation table if db is available
            db_opted_out = False
            if self.db:
                try:
                    conversations = (
                        self.db.query(SMSConversation)
                        .filter(
                            SMSConversation.company_id == company_id,
                            SMSConversation.customer_number == phone_number,
                        )
                        .all()
                    )
                    db_opted_out = any(c.is_opted_out for c in conversations)
                except Exception:
                    pass

            # Determine consent status
            is_opted_in = True

            # If there's an opt-out after the last opt-in, they're opted out
            if opt_out_record and opt_in_record:
                # Compare timestamps
                out_time = opt_out_record.get("timestamp", "")
                in_time = opt_in_record.get("timestamp", "")
                if out_time > in_time:
                    is_opted_in = False
            elif opt_out_record and not opt_in_record:
                is_opted_in = False

            # Database opt-out overrides
            if db_opted_out:
                is_opted_in = False

            consent_date = None
            consent_source = None
            if opt_in_record:
                consent_date = opt_in_record.get("timestamp")
                consent_source = opt_in_record.get("source")

            return {
                "status": "success",
                "is_opted_in": is_opted_in,
                "consent_date": consent_date,
                "consent_source": consent_source,
                "phone_number": phone_number,
            }

        except Exception as exc:
            logger.exception(
                "tcpa_check_consent_error",
                extra={
                    "company_id": company_id,
                    "phone_number": phone_number,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "is_opted_in": False,
                "consent_date": None,
                "consent_source": None,
                "error": f"Failed to check consent: {str(exc)[:200]}",
            }

    def record_consent(
        self,
        company_id: str,
        phone_number: str,
        consent_type: str,
        source: str,
    ) -> dict:
        """Record opt-in consent for a phone number.

        Args:
            company_id: Tenant company ID (BC-001).
            phone_number: Phone number to record consent for.
            consent_type: Type of consent — "explicit" (keyword),
                         "implicit" (inquiry), "manual" (agent).
            source: Source of consent — "sms", "web", "api", "agent".

        Returns:
            Dict with status and consent record details.
        """
        try:
            # Validate consent_type
            valid_consent_types = {"explicit", "implicit", "manual"}
            if consent_type not in valid_consent_types:
                return {
                    "status": "error",
                    "error": (
                        f"Invalid consent_type '{consent_type}'. "
                        f"Must be one of: {', '.join(sorted(valid_consent_types))}"
                    ),
                }

            # Validate source
            valid_sources = {"sms", "web", "api", "agent"}
            if source not in valid_sources:
                return {
                    "status": "error",
                    "error": (
                        f"Invalid source '{source}'. "
                        f"Must be one of: {', '.join(sorted(valid_sources))}"
                    ),
                }

            # Initialize company consent store
            if company_id not in _consent_store:
                _consent_store[company_id] = {}
            if phone_number not in _consent_store[company_id]:
                _consent_store[company_id][phone_number] = []

            # Record consent
            consent_record = {
                "id": str(uuid.uuid4()),
                "phone_number": phone_number,
                "consent_type": consent_type,
                "source": source,
                "action": "opt_in",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "company_id": company_id,
            }
            _consent_store[company_id][phone_number].append(consent_record)

            # Also update SMSConversation if db is available
            if self.db:
                try:
                    conversations = (
                        self.db.query(SMSConversation)
                        .filter(
                            SMSConversation.company_id == company_id,
                            SMSConversation.customer_number == phone_number,
                            SMSConversation.is_opted_out == True,  # noqa: E712
                        )
                        .all()
                    )
                    for conv in conversations:
                        conv.is_opted_out = False
                        conv.opt_out_keyword = None
                        conv.opt_out_at = None
                    self.db.commit()
                except Exception:
                    pass

            logger.info(
                "tcpa_consent_recorded",
                extra={
                    "company_id": company_id,
                    "phone_number": phone_number,
                    "consent_type": consent_type,
                    "source": source,
                },
            )

            return {
                "status": "recorded",
                "consent_id": consent_record["id"],
                "consent_type": consent_type,
                "source": source,
                "timestamp": consent_record["timestamp"],
            }

        except Exception as exc:
            logger.exception(
                "tcpa_record_consent_error",
                extra={
                    "company_id": company_id,
                    "phone_number": phone_number,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to record consent: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Quiet Hours
    # ═══════════════════════════════════════════════════════════

    def check_quiet_hours(
        self,
        company_id: str,
        phone_timezone: str,
    ) -> dict:
        """Check if current time is within quiet hours.

        Default quiet hours: 9pm - 9am in the recipient's local
        timezone. Messages should not be sent during quiet hours.

        Args:
            company_id: Tenant company ID (BC-001).
            phone_timezone: IANA timezone string (e.g. "America/New_York").

        Returns:
            Dict with is_quiet_hours, next_allowed_time, current_time.
        """
        try:
            import zoneinfo

            # Get current time in the phone's timezone
            try:
                tz = zoneinfo.ZoneInfo(phone_timezone)
            except (KeyError, zoneinfo.ZoneInfoNotFoundError):
                # Fallback to UTC
                tz = timezone.utc

            now_local = datetime.now(tz)
            current_time = now_local.time()

            # Determine quiet hours boundaries
            quiet_start = DEFAULT_QUIET_HOURS_START  # 9 PM
            quiet_end = DEFAULT_QUIET_HOURS_END  # 9 AM

            # Check if we're in quiet hours
            # Quiet hours span midnight: 9 PM -> 9 AM
            if quiet_start > quiet_end:
                # Spans midnight
                is_quiet = current_time >= quiet_start or current_time < quiet_end
            else:
                # Same day
                is_quiet = quiet_start <= current_time < quiet_end

            # Calculate next allowed time
            if is_quiet:
                if current_time >= quiet_start:
                    # Quiet hours started tonight, next allowed is tomorrow morning
                    next_allowed = datetime.combine(
                        now_local.date() + timedelta(days=1),
                        quiet_end,
                    )
                else:
                    # Before quiet_end this morning
                    next_allowed = datetime.combine(
                        now_local.date(),
                        quiet_end,
                    )
                next_allowed_dt = next_allowed.replace(tzinfo=tz)
            else:
                next_allowed_dt = now_local

            return {
                "status": "success",
                "is_quiet_hours": is_quiet,
                "next_allowed_time": next_allowed_dt.isoformat(),
                "current_time": now_local.isoformat(),
                "quiet_hours_start": quiet_start.isoformat(),
                "quiet_hours_end": quiet_end.isoformat(),
                "timezone": phone_timezone,
            }

        except Exception as exc:
            logger.exception(
                "tcpa_quiet_hours_error",
                extra={
                    "company_id": company_id,
                    "phone_timezone": phone_timezone,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "is_quiet_hours": False,
                "next_allowed_time": None,
                "current_time": None,
                "error": f"Failed to check quiet hours: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Pre-Send Compliance Check
    # ═══════════════════════════════════════════════════════════

    def enforce_before_send(
        self,
        company_id: str,
        phone_number: str,
        phone_timezone: str,
    ) -> dict:
        """Full TCPA check before sending: consent + quiet hours.

        This should be called before every outbound SMS/MMS to
        ensure TCPA compliance.

        Args:
            company_id: Tenant company ID (BC-001).
            phone_number: Recipient phone number.
            phone_timezone: IANA timezone string for the recipient.

        Returns:
            Dict with can_send, reason (if blocked), retry_at
            (if quiet hours).
        """
        try:
            # Step 1: Check consent
            consent_result = self.check_consent(company_id, phone_number)
            if consent_result.get("status") == "error":
                # On error, default to not opted in (conservative)
                return {
                    "status": "blocked",
                    "can_send": False,
                    "reason": "Unable to verify consent — blocked for safety",
                }

            if not consent_result.get("is_opted_in", False):
                return {
                    "status": "blocked",
                    "can_send": False,
                    "reason": "Recipient has not opted in or has opted out",
                }

            # Step 2: Check quiet hours
            quiet_result = self.check_quiet_hours(company_id, phone_timezone)
            if quiet_result.get("is_quiet_hours", False):
                # Increment blocked counter
                _quiet_hours_blocked[company_id] = (
                    _quiet_hours_blocked.get(company_id, 0) + 1
                )

                return {
                    "status": "blocked",
                    "can_send": False,
                    "reason": "Current time is within quiet hours",
                    "retry_at": quiet_result.get("next_allowed_time"),
                }

            return {
                "status": "allowed",
                "can_send": True,
                "reason": None,
                "retry_at": None,
            }

        except Exception as exc:
            logger.exception(
                "tcpa_enforce_error",
                extra={
                    "company_id": company_id,
                    "phone_number": phone_number,
                    "error": str(exc)[:500],
                },
            )
            # Conservative: block on error (BC-008: never crash,
            # but also don't accidentally violate TCPA)
            return {
                "status": "error",
                "can_send": False,
                "reason": f"Compliance check failed: {str(exc)[:200]}",
            }

    # ═══════════════════════════════════════════════════════════
    # Compliance Reporting
    # ═══════════════════════════════════════════════════════════

    def get_compliance_report(
        self,
        company_id: str,
    ) -> dict:
        """Generate TCPA compliance report for a tenant.

        Provides counts of opted-in, opted-out numbers, consent
        records, and quiet hours violations blocked.

        Args:
            company_id: Tenant company ID (BC-001).

        Returns:
            Dict with total_opted_in, total_opted_out,
            consent_records_count, quiet_hours_violations_blocked.
        """
        try:
            company_consents = _consent_store.get(company_id, {})
            total_opted_in = 0
            total_opted_out = 0
            consent_records_count = 0

            for phone_number, records in company_consents.items():
                consent_records_count += len(records)

                # Determine current status for this phone number
                latest_action = None
                for record in reversed(records):
                    if record.get("action") in ("opt_in", "opt_out"):
                        latest_action = record.get("action")
                        break

                if latest_action == "opt_in":
                    total_opted_in += 1
                elif latest_action == "opt_out":
                    total_opted_out += 1
                else:
                    # No explicit action — count as opted in if any record
                    if records:
                        total_opted_in += 1

            # Also count from database if available
            db_opted_in = 0
            db_opted_out = 0
            if self.db:
                try:
                    conversations = (
                        self.db.query(SMSConversation)
                        .filter(
                            SMSConversation.company_id == company_id,
                        )
                        .all()
                    )
                    for conv in conversations:
                        if conv.is_opted_out:
                            db_opted_out += 1
                        else:
                            db_opted_in += 1
                except Exception:
                    pass

            # Merge: use max of in-memory and db counts
            total_opted_in = max(total_opted_in, db_opted_in)
            total_opted_out = max(total_opted_out, db_opted_out)

            quiet_hours_blocked = _quiet_hours_blocked.get(company_id, 0)

            return {
                "status": "success",
                "company_id": company_id,
                "total_opted_in": total_opted_in,
                "total_opted_out": total_opted_out,
                "consent_records_count": consent_records_count,
                "quiet_hours_violations_blocked": quiet_hours_blocked,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.exception(
                "tcpa_compliance_report_error",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": f"Failed to generate compliance report: {str(exc)[:200]}",
                "total_opted_in": 0,
                "total_opted_out": 0,
                "consent_records_count": 0,
                "quiet_hours_violations_blocked": 0,
            }
