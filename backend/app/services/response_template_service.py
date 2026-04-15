"""
Response Template Storage Service (F-155)

CRUD operations for response templates per tenant.  Response templates are
distinct from prompt templates (SG-25): they represent *outbound messages*
to customers — greetings, apologies, escalation notices, refund confirmations,
technical support replies, and custom messages.

Each template supports ``{{variable}}`` placeholders that are safely rendered
with XSS sanitisation (GAP-010 FIX).  Templates are scoped to ``company_id``
(BC-001) and the service degrades gracefully on any error (BC-008).

Features:
- Full CRUD for response templates
- Template duplication (clone)
- Safe variable rendering with HTML / text sanitisation
- Best-template matching by intent, language, and sentiment
- Variable extraction and template validation
- Usage tracking with async increment
- Redis caching (key: ``resp_template:{company_id}:{template_id}``, TTL 1800)
- Five built-in default templates
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.exceptions import (
    InternalError,
    NotFoundError,
    ParwaBaseError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_CATEGORIES: Set[str] = {
    "greeting", "farewell", "apology", "escalation",
    "refund", "technical", "billing", "general", "custom",
}

VALID_LANGUAGES: Set[str] = {
    "en", "es", "fr", "de", "pt", "it", "nl", "ja", "zh",
    "ko", "ar", "hi", "ru", "pl", "tr", "sv",
}

VALID_VARIABLE_TYPES: Set[str] = {
    "string", "int", "float", "date", "email", "url",
}

# Regex helpers
_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# Redis cache TTL (30 minutes)
CACHE_TTL_SECONDS = 1800

# ══════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class TemplateVariable:
    """Describes a single template variable."""
    name: str
    description: str
    required: bool
    default_value: str | None
    type: str  # string, int, float, date, email, url


@dataclass
class TemplateValidationResult:
    """Result of validating template syntax and variables."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    variables_found: list[str]
    unclosed_variables: list[str]


@dataclass
class ResponseTemplate:
    """A stored response template scoped to a tenant."""
    id: str
    company_id: str
    name: str
    category: str  # greeting, farewell, apology, escalation, refund, technical, billing, general, custom
    intent_types: list[str]  # which intents this template applies to
    subject_template: str
    body_template: str  # supports {{variable}} placeholders
    variables: list[str]  # list of expected variables
    language: str  # en, es, fr, de, etc.
    is_active: bool
    usage_count: int
    last_used_at: datetime | None
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-friendly)."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "name": self.name,
            "category": self.category,
            "intent_types": self.intent_types,
            "subject_template": self.subject_template,
            "body_template": self.body_template,
            "variables": self.variables,
            "language": self.language,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "version": self.version,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ResponseTemplate:
        """Deserialise from a plain dict."""
        last_used = data.get("last_used_at")
        if isinstance(last_used, str):
            last_used = datetime.fromisoformat(last_used)
        elif last_used is not None:
            last_used = datetime.now(timezone.utc)

        created = data.get("created_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        elif created is None:
            created = datetime.now(timezone.utc)

        updated = data.get("updated_at")
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)
        elif updated is None:
            updated = datetime.now(timezone.utc)

        return cls(
            id=data["id"],
            company_id=data["company_id"],
            name=data["name"],
            category=data["category"],
            intent_types=data.get("intent_types", []),
            subject_template=data["subject_template"],
            body_template=data["body_template"],
            variables=data.get("variables", []),
            language=data.get("language", "en"),
            is_active=data.get("is_active", True),
            usage_count=data.get("usage_count", 0),
            last_used_at=last_used,
            version=data.get("version", 1),
            created_by=data.get("created_by", ""),
            created_at=created,
            updated_at=updated,
        )


# ══════════════════════════════════════════════════════════════════
# XSS SANITISATION (GAP-010 FIX)
# ══════════════════════════════════════════════════════════════════

_ALLOWED_TAGS: Set[str] = {
    "p", "br", "strong", "em", "ul", "ol", "li", "a", "span", "div",
}

_ALLOWED_ATTRS: Set[str] = {"href", "class", "style", "title"}

# Regex for stripping dangerous content
_RE_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_RE_EVENT_HANDLER = re.compile(r"on\w+\s*=\s*[\"'][^\"']*[\"']", re.IGNORECASE)
_RE_JAVASCRIPT = re.compile(r"javascript:", re.IGNORECASE)
_RE_HTML_TAG = re.compile(r"<(/?)(\w+)([^>]*)>")


def _clean_tag(
    match: re.Match,
    allowed_tags: Set[str],
    allowed_attrs: Set[str],
) -> str:
    """Filter a single HTML tag against whitelists.

    If the tag is not in the allowed set, the entire tag is removed.
    Attributes are also filtered to only those in the allowed set.
    """
    is_closing = match.group(1) == "/"
    tag_name = match.group(2).lower()
    attr_string = match.group(3)

    if tag_name not in allowed_tags:
        return ""

    if is_closing:
        return f"</{tag_name}>"

    # Filter attributes
    clean_attrs: list[str] = []
    for attr_match in re.finditer(r'(\w+)\s*=\s*(["\'][^"\']*["\']|\S+)', attr_string):
        attr_name = attr_match.group(1).lower()
        if attr_name in allowed_attrs:
            # Only allow safe attribute values (no javascript: etc.)
            attr_value = attr_match.group(2)
            if re.search(r"javascript:", attr_value, re.IGNORECASE):
                continue
            clean_attrs.append(f"{attr_name}={attr_value}")

    if clean_attrs:
        return f"<{tag_name} {' '.join(clean_attrs)}>"
    return f"<{tag_name}>"


def sanitize_template_variable(value: str, content_type: str = "text") -> str:
    """Sanitize template variable values to prevent XSS injection.

    GAP-010 FIX: All user-supplied variable values are sanitised before
    being interpolated into templates.

    Args:
        value: Raw variable value from user input.
        content_type: ``'text'`` auto-escapes HTML entities;
            ``'html'`` sanitises with a tag/attribute whitelist.

    Returns:
        Sanitised string safe for template interpolation.
    """
    if not isinstance(value, str):
        value = str(value)

    if content_type == "text":
        value = value.replace("&", "&amp;")
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")
        value = value.replace('"', "&quot;")
        value = value.replace("'", "&#x27;")
        return value

    if content_type == "html":
        # Remove script tags entirely
        value = _RE_SCRIPT.sub("", value)
        # Remove inline event handlers (onclick, onload, etc.)
        value = _RE_EVENT_HANDLER.sub("", value)
        # Remove javascript: URLs
        value = _RE_JAVASCRIPT.sub("", value)
        # Filter tags and attributes against whitelists
        value = _RE_HTML_TAG.sub(
            lambda m: _clean_tag(m, _ALLOWED_TAGS, _ALLOWED_ATTRS),
            value,
        )
        return value

    return value


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


def _extract_variables(content: str) -> list[str]:
    """Extract ``{{variable}}`` names from a template string.

    Returns:
        Sorted list of unique variable names.
    """
    return sorted(set(_VARIABLE_PATTERN.findall(content)))


def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required and non-empty."""
    if not company_id or not str(company_id).strip():
        raise ValidationError(
            message="company_id is required and cannot be empty",
        )


# ══════════════════════════════════════════════════════════════════
# DEFAULT TEMPLATES
# ══════════════════════════════════════════════════════════════════

_DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    # 1. Greeting
    {
        "name": "default_greeting",
        "category": "greeting",
        "intent_types": ["general"],
        "subject_template": "Welcome, {{customer_name}}!",
        "body_template": (
            "Hello {{customer_name}},\n\n"
            "Thank you for reaching out to {{company_name}} support. "
            "We're happy to help you with your inquiry.\n\n"
            "Our team will review your request and get back to you "
            "within {{response_time}}.\n\n"
            "Best regards,\n"
            "{{agent_name}}\n"
            "{{company_name}} Support Team"
        ),
        "language": "en",
    },
    # 2. Apology
    {
        "name": "default_apology",
        "category": "apology",
        "intent_types": ["complaint"],
        "subject_template": "We're Sorry, {{customer_name}}",
        "body_template": (
            "Dear {{customer_name}},\n\n"
            "We sincerely apologise for the inconvenience you've "
            "experienced with {{issue_description}}. This is not the "
            "level of service we strive to deliver.\n\n"
            "We understand how frustrating this must be, and we want "
            "to make things right. Our team is already looking into "
            "this matter and we expect to have a resolution within "
            "{{resolution_time}}.\n\n"
            "If there is anything else we can do in the meantime, "
            "please don't hesitate to let us know.\n\n"
            "Warm regards,\n"
            "{{agent_name}}\n"
            "{{company_name}} Support Team"
        ),
        "language": "en",
    },
    # 3. Escalation
    {
        "name": "default_escalation",
        "category": "escalation",
        "intent_types": ["escalation"],
        "subject_template": "Your Case Has Been Escalated — {{ticket_id}}",
        "body_template": (
            "Dear {{customer_name}},\n\n"
            "Thank you for your patience. We want to let you know that "
            "your case ({{ticket_id}}) has been escalated to our "
            "specialist team for further review.\n\n"
            "A dedicated team member will contact you within "
            "{{escalation_response_time}} with an update and next "
            "steps.\n\n"
            "We understand the urgency of your request and are "
            "prioritising it accordingly.\n\n"
            "Kind regards,\n"
            "{{agent_name}}\n"
            "{{company_name}} Support Team"
        ),
        "language": "en",
    },
    # 4. Refund Confirmation
    {
        "name": "default_refund_confirmation",
        "category": "refund",
        "intent_types": ["refund"],
        "subject_template": "Refund Confirmation — {{order_id}}",
        "body_template": (
            "Dear {{customer_name}},\n\n"
            "We're writing to confirm that a refund has been processed "
            "for your order {{order_id}}.\n\n"
            "Refund details:\n"
            "  - Amount: {{refund_amount}}\n"
            "  - Payment method: {{payment_method}}\n"
            "  - Reference: {{refund_reference}}\n"
            "  - Expected processing time: {{processing_time}}\n\n"
            "Please note that it may take 3-5 business days for the "
            "refund to appear on your statement, depending on your "
            "bank.\n\n"
            "If you have any questions about this refund, please "
            "reply to this message.\n\n"
            "Best regards,\n"
            "{{agent_name}}\n"
            "{{company_name}} Finance Team"
        ),
        "language": "en",
    },
    # 5. Technical Support
    {
        "name": "default_technical_support",
        "category": "technical",
        "intent_types": ["technical"],
        "subject_template": "Technical Support — {{issue_summary}}",
        "body_template": (
            "Hi {{customer_name}},\n\n"
            "Thank you for providing the details about the technical "
            "issue you're experiencing with {{product_or_service}}.\n\n"
            "Based on the information provided, here are the steps we "
            "recommend:\n\n"
            "{{troubleshooting_steps}}\n\n"
            "If these steps don't resolve the issue, please let us know "
            "and include:\n"
            "  - Any error messages you're seeing\n"
            "  - Screenshots (if applicable)\n"
            "  - Steps you've already tried\n\n"
            "Our technical team is standing by to assist further if "
            "needed.\n\n"
            "Best regards,\n"
            "{{agent_name}}\n"
            "{{company_name}} Technical Support"
        ),
        "language": "en",
    },
]


# ══════════════════════════════════════════════════════════════════
# KNOWN VARIABLE DEFINITIONS
# ══════════════════════════════════════════════════════════════════

_KNOWN_VARIABLES: Dict[str, TemplateVariable] = {
    "customer_name": TemplateVariable("customer_name", "Customer's full name", True, None, "string"),
    "company_name": TemplateVariable("company_name", "Company / brand name", True, None, "string"),
    "agent_name": TemplateVariable("agent_name", "Support agent name", False, "Support Team", "string"),
    "ticket_id": TemplateVariable("ticket_id", "Ticket reference number", False, None, "string"),
    "response_time": TemplateVariable("response_time", "Expected response time", False, "24 hours", "string"),
    "issue_description": TemplateVariable("issue_description", "Short description of the issue", False, None, "string"),
    "resolution_time": TemplateVariable("resolution_time", "Expected resolution timeframe", False, "48 hours", "string"),
    "escalation_response_time": TemplateVariable("escalation_response_time", "Escalation SLA window", False, "2 hours", "string"),
    "order_id": TemplateVariable("order_id", "Order reference number", False, None, "string"),
    "refund_amount": TemplateVariable("refund_amount", "Refund monetary amount", False, None, "string"),
    "payment_method": TemplateVariable("payment_method", "Payment method used", False, None, "string"),
    "refund_reference": TemplateVariable("refund_reference", "Refund transaction reference", False, None, "string"),
    "processing_time": TemplateVariable("processing_time", "Refund processing duration", False, "3-5 business days", "string"),
    "issue_summary": TemplateVariable("issue_summary", "One-line summary of the issue", True, None, "string"),
    "product_or_service": TemplateVariable("product_or_service", "Affected product or service", False, None, "string"),
    "troubleshooting_steps": TemplateVariable("troubleshooting_steps", "Step-by-step troubleshooting guide", False, None, "string"),
}


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class ResponseTemplateService:
    """CRUD and rendering service for per-tenant response templates.

    Storage is in-memory (class-level dict) with optional Redis caching
    for read-heavy workloads.  All operations are scoped to ``company_id``
    (BC-001) and every public method catches exceptions to honour BC-008.

    Args:
        db: Optional database session (reserved for future ORM migration).
        redis_client: Optional Redis client for caching.  When ``None``,
            the service falls back to pure in-memory storage.
    """

    # Class-level in-memory store (singleton pattern)
    _store: Dict[str, Dict[str, ResponseTemplate]] = {}
    _defaults_loaded: Dict[str, bool] = {}

    def __init__(self, db: Any = None, redis_client: Any = None) -> None:
        self.db = db
        self.redis_client = redis_client

    # ──────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────

    def _ensure_defaults(self, company_id: str) -> None:
        """Load built-in default templates for a company if not loaded."""
        if self.__class__._defaults_loaded.get(company_id):
            return

        if company_id not in self.__class__._store:
            self.__class__._store[company_id] = {}

        now = _now()
        for definition in _DEFAULT_TEMPLATES:
            # Check if already exists
            existing = any(
                t.name == definition["name"]
                for t in self.__class__._store[company_id].values()
            )
            if existing:
                continue

            subject_vars = _extract_variables(definition["subject_template"])
            body_vars = _extract_variables(definition["body_template"])
            all_vars = sorted(set(subject_vars + body_vars))

            template = ResponseTemplate(
                id=_generate_id(),
                company_id=company_id,
                name=definition["name"],
                category=definition["category"],
                intent_types=definition.get("intent_types", []),
                subject_template=definition["subject_template"],
                body_template=definition["body_template"],
                variables=all_vars,
                language=definition.get("language", "en"),
                is_active=True,
                usage_count=0,
                last_used_at=None,
                version=1,
                created_by="system",
                created_at=now,
                updated_at=now,
            )
            self.__class__._store[company_id][template.id] = template

        self.__class__._defaults_loaded[company_id] = True
        logger.info(
            "response_template_defaults_loaded",
            extra={"company_id": company_id, "defaults_count": len(_DEFAULT_TEMPLATES)},
        )

    async def _cache_get(self, company_id: str, template_id: str) -> Optional[ResponseTemplate]:
        """Try to fetch a template from Redis cache."""
        if self.redis_client is None:
            return None
        try:
            cache_key = f"resp_template:{company_id}:{template_id}"
            raw = await self.redis_client.get(cache_key)
            if raw:
                return ResponseTemplate.from_dict(json.loads(raw))
        except Exception as exc:
            logger.warning(
                "response_template_cache_get_failed",
                extra={"company_id": company_id, "template_id": template_id, "error": str(exc)},
            )
        return None

    async def _cache_set(self, template: ResponseTemplate) -> None:
        """Store a template in Redis cache."""
        if self.redis_client is None:
            return
        try:
            cache_key = f"resp_template:{template.company_id}:{template.id}"
            await self.redis_client.set(
                cache_key,
                json.dumps(template.to_dict()),
                ex=CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "response_template_cache_set_failed",
                extra={"template_id": template.id, "error": str(exc)},
            )

    async def _cache_delete(self, company_id: str, template_id: str) -> None:
        """Remove a template from Redis cache."""
        if self.redis_client is None:
            return
        try:
            cache_key = f"resp_template:{company_id}:{template_id}"
            await self.redis_client.delete(cache_key)
        except Exception as exc:
            logger.warning(
                "response_template_cache_delete_failed",
                extra={"company_id": company_id, "template_id": template_id, "error": str(exc)},
            )

    def _get_store(self, company_id: str) -> Dict[str, ResponseTemplate]:
        """Return the in-memory store for a company, ensuring defaults."""
        _validate_company_id(company_id)
        self._ensure_defaults(company_id)
        return self.__class__._store.setdefault(company_id, {})

    # ──────────────────────────────────────────────────────────────
    # CRUD operations
    # ──────────────────────────────────────────────────────────────

    async def create_template(
        self,
        company_id: str,
        template_data: dict,
    ) -> ResponseTemplate:
        """Create a new response template for a tenant.

        Args:
            company_id: Tenant identifier (BC-001).
            template_data: Dict containing template fields. Required keys:
                ``name``, ``category``, ``subject_template``, ``body_template``.
                Optional keys: ``intent_types``, ``language``, ``is_active``,
                ``created_by``.

        Returns:
            The created ``ResponseTemplate``.

        Raises:
            ValidationError: If required fields are missing or invalid.
        """
        try:
            store = self._get_store(company_id)

            # Validate required fields
            name = template_data.get("name", "").strip()
            if not name:
                raise ValidationError(message="Template name is required")

            category = template_data.get("category", "").strip().lower()
            if category not in VALID_CATEGORIES:
                raise ValidationError(
                    message=f"Invalid category '{category}'. "
                    f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
                )

            subject_template = template_data.get("subject_template", "")
            body_template = template_data.get("body_template", "")
            if not subject_template and not body_template:
                raise ValidationError(
                    message="At least one of subject_template or body_template is required",
                )

            language = template_data.get("language", "en").strip().lower()
            if language not in VALID_LANGUAGES:
                logger.warning(
                    "response_template_unknown_language",
                    extra={"language": language, "company_id": company_id},
                )

            intent_types = template_data.get("intent_types", [])
            if not isinstance(intent_types, list):
                intent_types = []

            # Extract variables
            subject_vars = _extract_variables(subject_template)
            body_vars = _extract_variables(body_template)
            all_vars = sorted(set(subject_vars + body_vars))

            now = _now()
            template = ResponseTemplate(
                id=_generate_id(),
                company_id=company_id,
                name=name,
                category=category,
                intent_types=intent_types,
                subject_template=subject_template,
                body_template=body_template,
                variables=all_vars,
                language=language,
                is_active=template_data.get("is_active", True),
                usage_count=0,
                last_used_at=None,
                version=1,
                created_by=template_data.get("created_by", ""),
                created_at=now,
                updated_at=now,
            )

            store[template.id] = template
            await self._cache_set(template)

            logger.info(
                "response_template_created",
                extra={
                    "template_id": template.id,
                    "company_id": company_id,
                    "name": name,
                    "category": category,
                },
            )
            return template

        except (ValidationError,):
            raise
        except Exception as exc:
            logger.error(
                "response_template_create_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            raise InternalError(message="Failed to create response template", details={"error": str(exc)})

    async def get_template(
        self,
        template_id: str,
        company_id: str,
    ) -> ResponseTemplate:
        """Retrieve a template by ID and company.

        Checks Redis cache first, falls back to in-memory store.

        Args:
            template_id: Template UUID.
            company_id: Tenant identifier (BC-001).

        Returns:
            The matched ``ResponseTemplate``.

        Raises:
            NotFoundError: If template does not exist for this tenant.
        """
        try:
            _validate_company_id(company_id)

            # Try cache first
            cached = await self._cache_get(company_id, template_id)
            if cached is not None:
                return cached

            store = self._get_store(company_id)
            template = store.get(template_id)
            if template is None:
                raise NotFoundError(
                    message=f"Response template '{template_id}' not found",
                )

            # Populate cache
            await self._cache_set(template)
            return template

        except (NotFoundError, ValidationError):
            raise
        except Exception as exc:
            logger.error(
                "response_template_get_failed",
                extra={"template_id": template_id, "company_id": company_id, "error": str(exc)},
            )
            raise InternalError(message="Failed to retrieve response template", details={"error": str(exc)})

    async def list_templates(
        self,
        company_id: str,
        category: str | None = None,
        language: str | None = None,
        active_only: bool = True,
    ) -> list[ResponseTemplate]:
        """List templates for a tenant with optional filters.

        Args:
            company_id: Tenant identifier (BC-001).
            category: Optional category filter.
            language: Optional language filter.
            active_only: Only return active templates (default ``True``).

        Returns:
            List of matching ``ResponseTemplate`` instances.
        """
        try:
            store = self._get_store(company_id)
            results: list[ResponseTemplate] = []

            for template in store.values():
                if active_only and not template.is_active:
                    continue
                if category and template.category != category.lower():
                    continue
                if language and template.language != language.lower():
                    continue
                results.append(template)

            # Sort by updated_at descending
            results.sort(key=lambda t: t.updated_at, reverse=True)
            return results

        except Exception as exc:
            logger.error(
                "response_template_list_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return []

    async def update_template(
        self,
        template_id: str,
        company_id: str,
        updates: dict,
    ) -> ResponseTemplate:
        """Update an existing response template.

        Args:
            template_id: Template UUID.
            company_id: Tenant identifier (BC-001).
            updates: Dict of fields to update. Supported keys:
                ``name``, ``category``, ``intent_types``, ``subject_template``,
                ``body_template``, ``language``, ``is_active``.

        Returns:
            The updated ``ResponseTemplate``.

        Raises:
            NotFoundError: If template doesn't exist.
            ValidationError: If update data is invalid.
        """
        try:
            store = self._get_store(company_id)
            template = store.get(template_id)
            if template is None:
                raise NotFoundError(
                    message=f"Response template '{template_id}' not found",
                )

            now = _now()
            modified = False

            # Apply updatable fields
            if "name" in updates and updates["name"]:
                template.name = str(updates["name"]).strip()
                modified = True

            if "category" in updates:
                cat = str(updates["category"]).strip().lower()
                if cat not in VALID_CATEGORIES:
                    raise ValidationError(
                        message=f"Invalid category '{cat}'. "
                        f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
                    )
                template.category = cat
                modified = True

            if "intent_types" in updates:
                new_intents = updates["intent_types"]
                if isinstance(new_intents, list):
                    template.intent_types = new_intents
                    modified = True

            if "subject_template" in updates:
                template.subject_template = str(updates["subject_template"])
                modified = True

            if "body_template" in updates:
                template.body_template = str(updates["body_template"])
                modified = True

            if "language" in updates:
                template.language = str(updates["language"]).strip().lower()
                modified = True

            if "is_active" in updates:
                template.is_active = bool(updates["is_active"])
                modified = True

            if modified:
                # Re-extract variables from updated templates
                subject_vars = _extract_variables(template.subject_template)
                body_vars = _extract_variables(template.body_template)
                template.variables = sorted(set(subject_vars + body_vars))

                template.version += 1
                template.updated_at = now

                await self._cache_set(template)

                logger.info(
                    "response_template_updated",
                    extra={
                        "template_id": template_id,
                        "company_id": company_id,
                        "version": template.version,
                    },
                )

            return template

        except (NotFoundError, ValidationError):
            raise
        except Exception as exc:
            logger.error(
                "response_template_update_failed",
                extra={"template_id": template_id, "company_id": company_id, "error": str(exc)},
            )
            raise InternalError(message="Failed to update response template", details={"error": str(exc)})

    async def delete_template(
        self,
        template_id: str,
        company_id: str,
    ) -> bool:
        """Delete a response template.

        Args:
            template_id: Template UUID.
            company_id: Tenant identifier (BC-001).

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        try:
            store = self._get_store(company_id)
            if template_id in store:
                del store[template_id]
                await self._cache_delete(company_id, template_id)
                logger.info(
                    "response_template_deleted",
                    extra={"template_id": template_id, "company_id": company_id},
                )
                return True
            return False

        except Exception as exc:
            logger.error(
                "response_template_delete_failed",
                extra={"template_id": template_id, "company_id": company_id, "error": str(exc)},
            )
            return False

    async def duplicate_template(
        self,
        template_id: str,
        company_id: str,
    ) -> ResponseTemplate:
        """Create a copy of an existing template.

        The duplicated template gets a new ID, version 1, and a
        ``(Copy)`` suffix on the name.

        Args:
            template_id: Template UUID to duplicate.
            company_id: Tenant identifier (BC-001).

        Returns:
            The new ``ResponseTemplate`` copy.

        Raises:
            NotFoundError: If source template doesn't exist.
        """
        try:
            original = await self.get_template(template_id, company_id)
            now = _now()

            copy = ResponseTemplate(
                id=_generate_id(),
                company_id=original.company_id,
                name=f"{original.name} (Copy)",
                category=original.category,
                intent_types=list(original.intent_types),
                subject_template=original.subject_template,
                body_template=original.body_template,
                variables=list(original.variables),
                language=original.language,
                is_active=False,  # Start inactive so user can review
                usage_count=0,
                last_used_at=None,
                version=1,
                created_by=original.created_by,
                created_at=now,
                updated_at=now,
            )

            store = self._get_store(company_id)
            store[copy.id] = copy
            await self._cache_set(copy)

            logger.info(
                "response_template_duplicated",
                extra={
                    "source_id": template_id,
                    "new_id": copy.id,
                    "company_id": company_id,
                },
            )
            return copy

        except (NotFoundError,):
            raise
        except Exception as exc:
            logger.error(
                "response_template_duplicate_failed",
                extra={"template_id": template_id, "company_id": company_id, "error": str(exc)},
            )
            raise InternalError(message="Failed to duplicate response template", details={"error": str(exc)})

    # ──────────────────────────────────────────────────────────────
    # Template operations
    # ──────────────────────────────────────────────────────────────

    async def render_template(
        self,
        template_id: str,
        company_id: str,
        variables: dict,
        content_type: str = "text",
    ) -> str:
        """Render a template by substituting ``{{variable}}`` placeholders.

        Missing variables are left as-is.  All variable values are
        sanitised via :func:`sanitize_template_variable` (GAP-010 FIX).

        Args:
            template_id: Template UUID.
            company_id: Tenant identifier (BC-001).
            variables: Mapping of variable name to raw value.
            content_type: ``'text'`` (auto-escape HTML) or ``'html'``
                (whitelist sanitisation). Defaults to ``'text'``.

        Returns:
            Rendered subject + body joined by two newlines.
        """
        try:
            template = await self.get_template(template_id, company_id)

            # Sanitise all variable values (GAP-010 FIX)
            safe_vars: Dict[str, str] = {}
            for key, value in variables.items():
                safe_vars[key] = sanitize_template_variable(str(value) if value is not None else "", content_type)

            def _replacer(match: re.Match) -> str:
                var_name = match.group(1)
                if var_name in safe_vars:
                    return safe_vars[var_name]
                # Leave missing variable as-is
                return match.group(0)

            rendered_subject = _VARIABLE_PATTERN.sub(_replacer, template.subject_template)
            rendered_body = _VARIABLE_PATTERN.sub(_replacer, template.body_template)

            # Increment usage
            await self.increment_usage(template_id)

            return f"{rendered_subject}\n\n{rendered_body}"

        except Exception as exc:
            logger.error(
                "response_template_render_failed",
                extra={"template_id": template_id, "company_id": company_id, "error": str(exc)},
            )
            # BC-008: Return a safe fallback rather than crashing
            return ""

    async def find_best_template(
        self,
        company_id: str,
        intent_type: str,
        language: str = "en",
        sentiment_score: float = 0.5,
    ) -> ResponseTemplate | None:
        """Find the best matching template for a given context.

        Scoring criteria:
        1. Intent type match (highest weight)
        2. Language match
        3. Sentiment-appropriate category (negative sentiment prefers
           apology/escalation; positive prefers greeting/general)
        4. Most recently updated

        Args:
            company_id: Tenant identifier (BC-001).
            intent_type: The classified intent of the message.
            language: Preferred response language (default ``'en'``).
            sentiment_score: Normalised sentiment score
                (0.0 = very negative, 1.0 = very positive).

        Returns:
            Best matching ``ResponseTemplate`` or ``None``.
        """
        try:
            templates = await self.list_templates(company_id, active_only=True)
            if not templates:
                return None

            # Map sentiment to preferred categories
            sentiment_category_boost: Dict[str, float] = {}
            if sentiment_score < 0.3:
                # Negative sentiment — boost apology and escalation
                sentiment_category_boost = {"apology": 2.0, "escalation": 1.5}
            elif sentiment_score > 0.7:
                # Positive sentiment — boost greeting and general
                sentiment_category_boost = {"greeting": 1.5, "general": 1.0}
            else:
                # Neutral — no strong preference
                sentiment_category_boost = {"general": 1.0}

            best_template: ResponseTemplate | None = None
            best_score = -1.0

            for template in templates:
                score = 0.0

                # 1. Intent match (up to 50 points)
                if intent_type in template.intent_types:
                    score += 50.0

                # 2. Language match (up to 30 points)
                if template.language == language:
                    score += 30.0

                # 3. Sentiment-appropriate category boost (up to 20 points)
                category_score = sentiment_category_boost.get(template.category, 0.0)
                score += category_score * 10.0

                # 4. Recency bonus (up to 5 points for very recent updates)
                age_hours = (_now() - template.updated_at).total_seconds() / 3600
                recency = max(0.0, 5.0 - (age_hours / 720))  # Decays over 30 days
                score += recency

                if score > best_score:
                    best_score = score
                    best_template = template

            if best_template is not None:
                logger.info(
                    "response_template_best_match",
                    extra={
                        "template_id": best_template.id,
                        "name": best_template.name,
                        "company_id": company_id,
                        "intent_type": intent_type,
                        "language": language,
                        "score": best_score,
                    },
                )

            return best_template

        except Exception as exc:
            logger.error(
                "response_template_find_best_failed",
                extra={"company_id": company_id, "intent_type": intent_type, "error": str(exc)},
            )
            return None

    async def get_template_variables(
        self,
        template_id: str,
        company_id: str,
    ) -> list[TemplateVariable]:
        """Extract and describe all variables from a template.

        For each ``{{variable}}`` found in the subject and body, returns
        a :class:`TemplateVariable` with metadata from the known variable
        registry. Unknown variables are returned with default metadata.

        Args:
            template_id: Template UUID.
            company_id: Tenant identifier (BC-001).

        Returns:
            List of :class:`TemplateVariable` instances.
        """
        try:
            template = await self.get_template(template_id, company_id)
            result: list[TemplateVariable] = []

            for var_name in template.variables:
                if var_name in _KNOWN_VARIABLES:
                    result.append(_KNOWN_VARIABLES[var_name])
                else:
                    result.append(TemplateVariable(
                        name=var_name,
                        description=f"Custom variable: {var_name}",
                        required=False,
                        default_value=None,
                        type="string",
                    ))

            return result

        except Exception as exc:
            logger.error(
                "response_template_get_variables_failed",
                extra={"template_id": template_id, "company_id": company_id, "error": str(exc)},
            )
            return []

    async def validate_template(
        self,
        template_content: str,
    ) -> TemplateValidationResult:
        """Validate template syntax and variable usage.

        Checks:
        - Balanced ``{{`` and ``}}`` braces
        - Known variable names (warns for unknown ones)
        - Syntax errors (unclosed tags)

        Args:
            template_content: The template string to validate.

        Returns:
            A :class:`TemplateValidationResult` with details.
        """
        try:
            errors: list[str] = []
            warnings: list[str] = []
            variables_found = _extract_variables(template_content)

            # Check for unclosed variable tags and orphan braces
            unclosed: list[str] = []

            # Count all {{ and }} occurrences
            all_open = list(re.finditer(r"\{\{", template_content))
            all_close = list(re.finditer(r"\}\}", template_content))

            open_count = len(all_open)
            close_count = len(all_close)

            if open_count != close_count:
                if open_count > close_count:
                    unclosed_count = open_count - close_count
                    errors.append(
                        f"Unclosed variable tags detected: "
                        f"{unclosed_count} more opening braces than closing"
                    )
                    for m in all_open[close_count:]:
                        unclosed.append("{{")
                else:
                    errors.append(
                        f"Orphan closing braces detected: "
                        f"{close_count - open_count} more closing braces than opening"
                    )

            # Check for whitespace or special chars inside braces
            for m in re.finditer(r"\{\{([^}]*)\}\}", template_content):
                inner = m.group(1).strip()
                if not inner:
                    errors.append(f"Empty variable tag at position {m.start()}")
                elif not re.match(r"^\w+$", inner):
                    warnings.append(
                        f"Variable '{inner}' contains non-word characters; "
                        f"consider using only letters, digits, and underscores"
                    )

            # Warn about unknown variables
            known_var_names = set(_KNOWN_VARIABLES.keys())
            for var_name in variables_found:
                if var_name not in known_var_names:
                    warnings.append(f"Unknown variable: '{var_name}' — not in the standard variable registry")

            is_valid = len(errors) == 0

            return TemplateValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                variables_found=variables_found,
                unclosed_variables=unclosed,
            )

        except Exception as exc:
            logger.error(
                "response_template_validate_failed",
                extra={"error": str(exc)},
            )
            return TemplateValidationResult(
                is_valid=False,
                errors=[f"Validation failed: {str(exc)}"],
                warnings=[],
                variables_found=[],
                unclosed_variables=[],
            )

    async def increment_usage(self, template_id: str) -> None:
        """Increment the usage counter for a template.

        Updates ``usage_count`` and ``last_used_at`` in the in-memory
        store and invalidates the Redis cache so the next read fetches
        fresh data.

        Args:
            template_id: Template UUID.
        """
        try:
            # Search across all companies for this template
            for company_id, store in self.__class__._store.items():
                template = store.get(template_id)
                if template is not None:
                    template.usage_count += 1
                    template.last_used_at = _now()
                    template.updated_at = _now()
                    await self._cache_delete(company_id, template_id)
                    break

        except Exception as exc:
            logger.warning(
                "response_template_increment_usage_failed",
                extra={"template_id": template_id, "error": str(exc)},
            )
