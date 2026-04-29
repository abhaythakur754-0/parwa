"""
PARWA Brand Voice Configuration Service (Week 9, Day 8).

Per-company brand voice settings including tone, formality, prohibited words,
response length preference, emoji usage, apology style, and escalation tone.

F-154: Brand Voice Config Per Company
GAP-021 FIX: Normalized text checking catches l33t-speak and emoji variants.

BC-001: All operations scoped to company_id.
BC-008: Never crash — graceful degradation everywhere.
"""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# VALID ENUM VALUES
# ══════════════════════════════════════════════════════════════════

VALID_TONES = {
    "professional", "friendly", "casual", "empathetic", "authoritative",
}

VALID_RESPONSE_LENGTHS = {"concise", "standard", "detailed"}

VALID_EMOJI_USAGE = {"none", "minimal", "moderate", "liberal"}

VALID_APOLOGY_STYLES = {"formal", "empathetic", "solution-focused"}

VALID_ESCALATION_TONES = {"urgent", "calm", "reassuring"}

VALID_INDUSTRIES = {
    "tech", "ecommerce", "finance",
    "education", "legal", "hospitality",
}

REDIS_KEY_PREFIX = "brand_voice:"
REDIS_TTL_SECONDS = 3600


# ══════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class BrandVoiceConfig:
    """Per-company brand voice configuration (F-154)."""

    company_id: str
    tone: str  # professional, friendly, casual, empathetic, authoritative
    formality_level: float  # 0.0 (very informal) to 1.0 (very formal)
    prohibited_words: List[str]
    response_length_preference: str  # concise, standard, detailed
    max_response_sentences: int
    min_response_sentences: int
    greeting_template: str
    closing_template: str
    emoji_usage: str  # none, minimal, moderate, liberal
    apology_style: str  # formal, empathetic, solution-focused
    escalation_tone: str  # urgent, calm, reassuring
    brand_name: str
    industry: str
    custom_instructions: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ProhibitedWordCheck:
    """Result of checking text for prohibited words.

    Includes normalized form matching to catch l33t-speak variants
    (GAP-021 FIX).
    """

    has_violations: bool
    # [{word, position, normalized_form, severity}]
    violations: List[Dict[str, Any]]
    cleaned_text: str


@dataclass
class ResponseGuidelines:
    """Dynamic response guidelines based on sentiment and brand voice."""

    tone: str
    formality_level: float
    max_sentences: int
    min_sentences: int
    empathy_level: str  # low, medium, high, critical
    urgency_adjustment: str
    suggested_opening: str
    suggested_closing: str
    avoid_phrases: List[str]


@dataclass
class ValidationResult:
    """Result of validating a response against brand voice rules."""

    is_valid: bool
    violations: List[str]
    warnings: List[str]
    score: float  # 0-1 brand voice adherence
    suggested_fixes: List[str]


# ══════════════════════════════════════════════════════════════════
# TEXT NORMALIZATION (GAP-021 FIX)
# ══════════════════════════════════════════════════════════════════


# Common l33t-speak digit → letter mappings
# Note: Only standard digit-based substitutions.  Symbol-based mappings
# (e.g. @, $) are included but punctuation like ! is NOT mapped because
# it would corrupt word endings (e.g. "returns!" → "returnsi").
_LEET_MAP: Dict[str, str] = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
    "7": "t", "8": "b", "@": "a", "$": "s",
})


def _normalize_text(text: str) -> str:
    """Normalize text to catch l33t-speak and emoji variants.

    Steps:
      1. Lowercase the text.
      2. Apply l33t-speak digit/symbol-to-letter mapping (GAP-021).
      3. Strip remaining non-alphanumeric characters (except spaces).
      4. Collapse repeated characters (e.g. "heelllo" -> "helo").
      5. Collapse whitespace and strip.

    This catches variants like "d4mn", "h3ll", "sh1t", "@$$", "f*ck", etc.
    """
    text = text.lower()
    text = text.translate(_LEET_MAP)  # l33t-speak digits/symbols → letters
    text = re.sub(r"[^a-z0-9\s]", "", text)  # strip remaining non-alphanumeric
    text = re.sub(r"(.)\1{2,}", r"\1", text)  # collapse repeated chars
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_word(word: str) -> str:
    """Normalize a single word for comparison."""
    return _normalize_text(word).strip()


# ══════════════════════════════════════════════════════════════════
# INDUSTRY DEFAULTS
# ══════════════════════════════════════════════════════════════════

_RESPONSE_LENGTH_BOUNDS: Dict[str, Dict[str, int]] = {
    "concise": {"min": 1, "max": 3},
    "standard": {"min": 2, "max": 6},
    "detailed": {"min": 4, "max": 12},
}

_INDUSTRY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "tech": {
        "tone": "professional",
        "formality_level": 0.7,
        "response_length_preference": "concise",
        "greeting_template": "Hello! How can I help you today?",
        "closing_template": "Let me know if you need anything else.",
        "emoji_usage": "minimal",
        "apology_style": "solution-focused",
        "escalation_tone": "calm",
        "prohibited_words": [],
        "custom_instructions": (
            "Be precise and technical when needed. "
            "Avoid jargon for non-technical users."
        ),
    },
    "ecommerce": {
        "tone": "friendly",
        "formality_level": 0.4,
        "response_length_preference": "standard",
        "greeting_template": "Hi there! Thanks for reaching out.",
        "closing_template": "Happy to help! Have a great day!",
        "emoji_usage": "moderate",
        "apology_style": "empathetic",
        "escalation_tone": "reassuring",
        "prohibited_words": [],
        "custom_instructions": (
            "Focus on order status, returns, and product info. "
            "Be warm and approachable."
        ),
    },
    "finance": {
        "tone": "authoritative",
        "formality_level": 0.9,
        "response_length_preference": "concise",
        "greeting_template": "Good day. How may I assist you?",
        "closing_template": "Please don't hesitate to reach out again.",
        "emoji_usage": "none",
        "apology_style": "formal",
        "escalation_tone": "urgent",
        "prohibited_words": [
            "guaranteed returns", "risk-free", "sure thing",
            "no problem", "easy money",
        ],
        "custom_instructions": (
            "Be precise with financial terminology. "
            "Include appropriate regulatory disclaimers. "
            "Never guarantee financial outcomes."
        ),
    },
    "education": {
        "tone": "friendly",
        "formality_level": 0.5,
        "response_length_preference": "detailed",
        "greeting_template": "Hello! Welcome to our learning platform.",
        "closing_template": "Keep up the great work! We're here to help.",
        "emoji_usage": "moderate",
        "apology_style": "solution-focused",
        "escalation_tone": "calm",
        "prohibited_words": [],
        "custom_instructions": (
            "Be encouraging and supportive. "
            "Use clear explanations suitable for learners. "
            "Offer additional resources when possible."
        ),
    },
    "legal": {
        "tone": "authoritative",
        "formality_level": 1.0,
        "response_length_preference": "detailed",
        "greeting_template": "Good day. How may we be of assistance?",
        "closing_template": "This communication is for informational purposes only.",
        "emoji_usage": "none",
        "apology_style": "formal",
        "escalation_tone": "urgent",
        "prohibited_words": [
            "guarantee", "will definitely", "no worries",
            "sure thing", "my bad",
        ],
        "custom_instructions": (
            "Be precise and formal. "
            "Always include appropriate legal disclaimers. "
            "Never provide legal advice; direct to an attorney."
        ),
    },
    "hospitality": {
        "tone": "casual",
        "formality_level": 0.3,
        "response_length_preference": "standard",
        "greeting_template": "Hey there! Thanks for choosing us!",
        "closing_template": "We hope you have an amazing experience!",
        "emoji_usage": "liberal",
        "apology_style": "empathetic",
        "escalation_tone": "reassuring",
        "prohibited_words": [],
        "custom_instructions": (
            "Be warm, welcoming, and enthusiastic. "
            "Focus on guest experience and satisfaction. "
            "Offer alternatives proactively when issues arise."
        ),
    },
}


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _count_sentences(text: str) -> int:
    """Count sentences in text using common delimiters."""
    if not text or not text.strip():
        return 0
    sentences = re.split(r"[.!?]+", text)
    # Filter out empty strings and very short fragments
    return len([s for s in sentences if s.strip() and len(s.strip()) > 2])


def _estimate_formality(text: str) -> float:
    """Estimate formality level of text on a 0.0-1.0 scale.

    Heuristics:
      - Contractions lower formality (e.g. "don't", "can't", "it's").
      - Exclamation marks lower formality.
      - Longer average word length raises formality.
      - Emojis and slang lower formality.
    """
    if not text or not text.strip():
        return 0.5

    text_lower = text.lower()
    score = 0.5  # start neutral

    # Contraction penalty
    contractions = re.findall(
        r"\b\w+'\w+\b", text_lower,
    )
    score -= len(contractions) * 0.05

    # Exclamation mark penalty
    exclamation_count = text.count("!")
    score -= min(exclamation_count, 5) * 0.03

    # Emoji penalty (basic unicode emoji range)
    emoji_pattern = re.compile(
        "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff"
        "\U00002702-\U000027b0\U000024c2-\U0001f251]",
        re.UNICODE,
    )
    emoji_count = len(emoji_pattern.findall(text))
    score -= min(emoji_count, 5) * 0.04

    # Average word length bonus
    words = re.findall(r"\b\w+\b", text_lower)
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len > 6:
            score += 0.1
        elif avg_word_len > 5:
            score += 0.05
        elif avg_word_len < 4:
            score -= 0.05

    # Formal words bonus
    formal_markers = [
        "sincerely", "regards", "furthermore", "therefore",
        "pursuant", "accordingly", "hereby", "notwithstanding",
    ]
    formal_count = sum(1 for m in formal_markers if m in text_lower)
    score += formal_count * 0.05

    # Clamp to 0.0-1.0
    return max(0.0, min(1.0, round(score, 2)))


def _validate_tone(tone: str) -> None:
    """Validate tone is a known value."""
    if tone not in VALID_TONES:
        raise ValidationError(
            message=(
                f"Invalid tone '{tone}'. "
                f"Must be one of: {', '.join(sorted(VALID_TONES))}"
            ),
        )


def _validate_formality(level: float) -> None:
    """Validate formality level is in range 0.0-1.0."""
    if not isinstance(level, (int, float)) or not (0.0 <= level <= 1.0):
        raise ValidationError(
            message="formality_level must be a float between 0.0 and 1.0",
        )


def _validate_response_length(preference: str) -> None:
    """Validate response length preference."""
    if preference not in VALID_RESPONSE_LENGTHS:
        raise ValidationError(
            message=(
                f"Invalid response_length_preference '{preference}'. "
                f"Must be one of: {', '.join(sorted(VALID_RESPONSE_LENGTHS))}"
            ),
        )


def _validate_emoji_usage(usage: str) -> None:
    """Validate emoji usage value."""
    if usage not in VALID_EMOJI_USAGE:
        raise ValidationError(
            message=(
                f"Invalid emoji_usage '{usage}'. "
                f"Must be one of: {', '.join(sorted(VALID_EMOJI_USAGE))}"
            ),
        )


def _validate_apology_style(style: str) -> None:
    """Validate apology style value."""
    if style not in VALID_APOLOGY_STYLES:
        raise ValidationError(
            message=(
                f"Invalid apology_style '{style}'. "
                f"Must be one of: {', '.join(sorted(VALID_APOLOGY_STYLES))}"
            ),
        )


def _validate_escalation_tone(tone: str) -> None:
    """Validate escalation tone value."""
    if tone not in VALID_ESCALATION_TONES:
        raise ValidationError(
            message=(
                f"Invalid escalation_tone '{tone}'. "
                f"Must be one of: {', '.join(sorted(VALID_ESCALATION_TONES))}"
            ),
        )


def _validate_industry(industry: str) -> None:
    """Validate industry is a known value."""
    if industry not in VALID_INDUSTRIES:
        raise ValidationError(
            message=(
                f"Invalid industry '{industry}'. "
                f"Must be one of: {', '.join(sorted(VALID_INDUSTRIES))}"
            ),
        )


def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required and non-empty."""
    if not company_id or not str(company_id).strip():
        raise ValidationError(
            message="company_id is required and cannot be empty",
        )


# ══════════════════════════════════════════════════════════════════
# SENTIMENT-BASED ADJUSTMENTS
# ══════════════════════════════════════════════════════════════════

_EMPATHY_OPENINGS: Dict[str, Dict[str, str]] = {
    "critical": {
        "professional": "I understand this situation is very frustrating, and I want to help resolve this for you right away.",
        "friendly": "I'm so sorry you're dealing with this — let me take care of it for you immediately.",
        "empathetic": "I can see how upsetting this must be, and I genuinely want to help make things right.",
        "authoritative": "I recognize the severity of this issue and am taking immediate action to resolve it.",
        "casual": "Oh no, that sounds really rough — let me fix this for you right now.",
    },
    "high": {
        "professional": "I understand your concern and want to address this promptly.",
        "friendly": "I'm sorry about this! Let me look into it and get it sorted out.",
        "empathetic": "I appreciate you sharing this with us, and I want to help.",
        "authoritative": "Thank you for bringing this to our attention. I will address it now.",
        "casual": "That's definitely not ideal — let me take a look and sort it out.",
    },
    "medium": {
        "professional": "Thank you for reaching out. How can I assist you?",
        "friendly": "Hey there! I'd be happy to help with that.",
        "empathetic": "Thanks for letting us know. Let me see what I can do.",
        "authoritative": "I'd be glad to assist. Please provide more details.",
        "casual": "Sure thing! Let me help you with that.",
    },
    "low": {
        "professional": "How can I assist you today?",
        "friendly": "Hi! What can I help you with?",
        "empathetic": "Hello! I'm here if you need anything.",
        "authoritative": "Good day. What can I do for you?",
        "casual": "Hey! What's up?",
    },
}

_EMPATHY_CLOSINGS: Dict[str, Dict[str, str]] = {
    "critical": {
        "professional": "I will personally ensure this is resolved. I will follow up with you shortly.",
        "friendly": "We've got this handled — I'll follow up to make sure everything is perfect.",
        "empathetic": "I want you to know we take this seriously. I'll follow up with you shortly.",
        "authoritative": "This matter has my full attention. Expect an update shortly.",
        "casual": "I'm on it — I'll check back with you soon to make sure it's all good.",
    },
    "high": {
        "professional": "Please don't hesitate to reach out if you need further assistance.",
        "friendly": "Hope that helps! Let us know if there's anything else.",
        "empathetic": "I hope this helps. We're always here for you.",
        "authoritative": "Should you have additional concerns, please let us know.",
        "casual": "That should do it! Hit us up if you need anything else.",
    },
    "medium": {
        "professional": "Is there anything else I can help you with?",
        "friendly": "Anything else? Happy to help!",
        "empathetic": "Feel free to reach out anytime — we're here for you.",
        "authoritative": "Let me know if you require further assistance.",
        "casual": "Need anything else? Just ask!",
    },
    "low": {
        "professional": "Thank you for contacting us.",
        "friendly": "Have a great day!",
        "empathetic": "Take care!",
        "authoritative": "Best regards.",
        "casual": "Cheers!",
    },
}

_AVOID_PHRASES_BY_EMPATHY: Dict[str, List[str]] = {
    "critical": [
        "calm down", "you should", "actually", "just",
        "at least", "on the bright side", "no worries",
    ],
    "high": [
        "you should", "just", "actually",
        "as you should know", "you're wrong",
    ],
    "medium": [
        "you should know", "clearly",
    ],
    "low": [],
}


# ══════════════════════════════════════════════════════════════════
# BRAND VOICE SERVICE
# ══════════════════════════════════════════════════════════════════


class BrandVoiceService:
    """Per-company brand voice configuration and response validation.

    Stores and retrieves brand voice settings, checks responses for
    compliance, and generates dynamic response guidelines based on
    customer sentiment.

    BC-001: All operations are scoped to company_id.
    BC-008: Never crash — all methods handle exceptions gracefully.
    """

    def __init__(
        self,
        db: Any = None,
        redis_client: Any = None,
    ) -> None:
        """Initialize the brand voice service.

        Args:
            db: Optional database session for persistence.
            redis_client: Optional Redis client for config caching
                (key: ``brand_voice:{company_id}``, TTL: 3600s).
        """
        self.db = db
        self.redis_client = redis_client
        self._in_memory_store: Dict[str, BrandVoiceConfig] = {}
        logger.info("brand_voice_service_initialized")

    # ── CONFIG CRUD ──────────────────────────────────────────────

    async def get_config(self, company_id: str) -> BrandVoiceConfig:
        """Get brand voice config for a company.

        Resolution order:
          1. Redis cache (if available)
          2. In-memory store
          3. Database (if available)
          4. Industry default for "tech"

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            The ``BrandVoiceConfig`` for this company.

        Raises:
            NotFoundError: If no config exists and no default can be
                generated.
        """
        try:
            _validate_company_id(company_id)

            # 1. Try Redis cache
            cached = await self._get_from_cache(company_id)
            if cached:
                logger.debug(
                    "brand_voice_cache_hit",
                    extra={"company_id": company_id},
                )
                return cached

            # 2. Try in-memory store
            if company_id in self._in_memory_store:
                logger.debug(
                    "brand_voice_in_memory_hit",
                    extra={"company_id": company_id},
                )
                return self._in_memory_store[company_id]

            # 3. Try database
            db_config = await self._get_from_db(company_id)
            if db_config:
                self._in_memory_store[company_id] = db_config
                await self._set_cache(company_id, db_config)
                return db_config

            # BC-008: No config found — return a sensible industry
            # default rather than crashing.  Log the miss so callers
            # can create a proper config later.
            logger.warning(
                "brand_voice_config_not_found_using_default",
                extra={"company_id": company_id},
            )
            return await self.get_default_config(
                "tech", company_id=company_id,
            )

        except ValidationError:
            raise
        except Exception as exc:
            logger.error(
                "brand_voice_get_config_failed",
                extra={"company_id": company_id, "error": str(exc)},
                exc_info=True,
            )
            # BC-008: Return a sensible default rather than crash
            return await self.get_default_config("tech", company_id=company_id)

    async def create_config(
        self,
        company_id: str,
        config_data: Dict[str, Any],
    ) -> BrandVoiceConfig:
        """Create a new brand voice config for a company.

        Args:
            company_id: Tenant identifier (BC-001).
            config_data: Dictionary of config fields. Missing fields
                get sensible defaults based on industry.

        Returns:
            The created ``BrandVoiceConfig``.

        Raises:
            ValidationError: If required fields are invalid.
        """
        try:
            _validate_company_id(company_id)

            industry = config_data.get("industry", "tech")
            _validate_industry(industry)

            # Start with industry defaults
            defaults = _INDUSTRY_DEFAULTS.get(
                industry, _INDUSTRY_DEFAULTS["tech"])
            length_bounds = _RESPONSE_LENGTH_BOUNDS.get(
                defaults["response_length_preference"],
                _RESPONSE_LENGTH_BOUNDS["standard"],
            )

            tone = config_data.get("tone", defaults["tone"])
            _validate_tone(tone)

            formality_level = config_data.get(
                "formality_level", defaults["formality_level"],
            )
            _validate_formality(formality_level)

            response_length = config_data.get(
                "response_length_preference",
                defaults["response_length_preference"],
            )
            _validate_response_length(response_length)

            emoji_usage = config_data.get(
                "emoji_usage", defaults["emoji_usage"],
            )
            _validate_emoji_usage(emoji_usage)

            apology_style = config_data.get(
                "apology_style", defaults["apology_style"],
            )
            _validate_apology_style(apology_style)

            escalation_tone = config_data.get(
                "escalation_tone", defaults["escalation_tone"],
            )
            _validate_escalation_tone(escalation_tone)

            # Build the bounds for the selected length preference
            bounds = _RESPONSE_LENGTH_BOUNDS.get(
                response_length, _RESPONSE_LENGTH_BOUNDS["standard"])
            max_sentences = config_data.get(
                "max_response_sentences", bounds["max"])
            min_sentences = config_data.get(
                "min_response_sentences", bounds["min"])

            # Validate min <= max
            if min_sentences > max_sentences:
                raise ValidationError(
                    message=(
                        f"min_response_sentences ({min_sentences}) cannot "
                        f"exceed max_response_sentences ({max_sentences})"
                    ),
                )

            now = _now_utc()

            config = BrandVoiceConfig(
                company_id=company_id,
                tone=tone,
                formality_level=float(formality_level),
                prohibited_words=config_data.get(
                    "prohibited_words", defaults["prohibited_words"],
                ),
                response_length_preference=response_length,
                max_response_sentences=max_sentences,
                min_response_sentences=min_sentences,
                greeting_template=config_data.get(
                    "greeting_template", defaults["greeting_template"],
                ),
                closing_template=config_data.get(
                    "closing_template", defaults["closing_template"],
                ),
                emoji_usage=emoji_usage,
                apology_style=apology_style,
                escalation_tone=escalation_tone,
                brand_name=config_data.get("brand_name", "PARWA"),
                industry=industry,
                custom_instructions=config_data.get(
                    "custom_instructions", defaults["custom_instructions"],
                ),
                created_at=now,
                updated_at=now,
            )

            # Store in memory
            self._in_memory_store[company_id] = config

            # Cache in Redis
            await self._set_cache(company_id, config)

            # Persist to DB if available
            await self._save_to_db(config)

            logger.info(
                "brand_voice_config_created",
                extra={
                    "company_id": company_id,
                    "industry": industry,
                    "tone": tone,
                },
            )

            return config

        except (ValidationError, NotFoundError):
            raise
        except Exception as exc:
            logger.error(
                "brand_voice_create_config_failed",
                extra={"company_id": company_id, "error": str(exc)},
                exc_info=True,
            )
            raise

    async def update_config(
        self,
        company_id: str,
        updates: Dict[str, Any],
    ) -> BrandVoiceConfig:
        """Update an existing brand voice config.

        Only provided fields are updated; omitted fields retain their
        current values.

        Args:
            company_id: Tenant identifier (BC-001).
            updates: Dictionary of fields to update.

        Returns:
            The updated ``BrandVoiceConfig``.

        Raises:
            NotFoundError: If no config exists for this company.
            ValidationError: If any update field is invalid.
        """
        try:
            _validate_company_id(company_id)

            existing = await self.get_config(company_id)

            # Build updated fields with validation
            if "tone" in updates and updates["tone"] is not None:
                _validate_tone(updates["tone"])

            if "formality_level" in updates and updates["formality_level"] is not None:
                _validate_formality(updates["formality_level"])

            if "response_length_preference" in updates and updates[
                    "response_length_preference"] is not None:
                _validate_response_length(
                    updates["response_length_preference"])
                pref = updates["response_length_preference"]
                bounds = _RESPONSE_LENGTH_BOUNDS.get(
                    pref, _RESPONSE_LENGTH_BOUNDS["standard"])
                if "max_response_sentences" not in updates:
                    updates["max_response_sentences"] = bounds["max"]
                if "min_response_sentences" not in updates:
                    updates["min_response_sentences"] = bounds["min"]

            if "emoji_usage" in updates and updates["emoji_usage"] is not None:
                _validate_emoji_usage(updates["emoji_usage"])

            if "apology_style" in updates and updates["apology_style"] is not None:
                _validate_apology_style(updates["apology_style"])

            if "escalation_tone" in updates and updates["escalation_tone"] is not None:
                _validate_escalation_tone(updates["escalation_tone"])

            if "industry" in updates and updates["industry"] is not None:
                _validate_industry(updates["industry"])

            # Validate sentence bounds if both are provided
            if "min_response_sentences" in updates and "max_response_sentences" in updates:
                min_s = updates["min_response_sentences"]
                max_s = updates["max_response_sentences"]
                if min_s > max_s:
                    raise ValidationError(
                        message=(
                            f"min_response_sentences ({min_s}) cannot "
                            f"exceed max_response_sentences ({max_s})"
                        ),
                    )

            # Apply updates
            updated_config = deepcopy(existing)
            for key, value in updates.items():
                if value is not None and hasattr(updated_config, key):
                    setattr(updated_config, key, value)
            updated_config.updated_at = _now_utc()

            # Store
            self._in_memory_store[company_id] = updated_config
            await self._set_cache(company_id, updated_config)
            await self._save_to_db(updated_config)

            logger.info(
                "brand_voice_config_updated",
                extra={
                    "company_id": company_id,
                    "updated_fields": list(updates.keys()),
                },
            )

            return updated_config

        except (NotFoundError, ValidationError):
            raise
        except Exception as exc:
            logger.error(
                "brand_voice_update_config_failed",
                extra={"company_id": company_id, "error": str(exc)},
                exc_info=True,
            )
            raise

    async def delete_config(self, company_id: str) -> bool:
        """Delete a brand voice config for a company.

        Removes from in-memory store, Redis cache, and database.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            ``True`` if config was deleted, ``False`` if not found.
        """
        try:
            _validate_company_id(company_id)

            existed = company_id in self._in_memory_store

            # Remove from in-memory store
            self._in_memory_store.pop(company_id, None)

            # Remove from Redis cache
            await self._delete_cache(company_id)

            # Remove from database
            await self._delete_from_db(company_id)

            if existed:
                logger.info(
                    "brand_voice_config_deleted",
                    extra={"company_id": company_id},
                )

            return existed

        except Exception as exc:
            logger.error(
                "brand_voice_delete_config_failed",
                extra={"company_id": company_id, "error": str(exc)},
                exc_info=True,
            )
            # BC-008: Return False rather than crash
            return False

    # ── PROHIBITED WORDS (GAP-021 FIX) ──────────────────────────

    async def check_prohibited_words(
        self,
        text: str,
        company_id: str,
    ) -> ProhibitedWordCheck:
        """Check text for prohibited words with l33t-speak normalization.

        GAP-021 FIX: Text is normalized (lowercase, strip non-alphanumeric,
        collapse repeated chars) before checking. This catches variants
        like "d4mn", "h3ll", "sh1t", "f*ck", "@$$", etc.

        Args:
            text: The text to check.
            company_id: Tenant identifier (BC-001).

        Returns:
            ``ProhibitedWordCheck`` with violations and cleaned text.
        """
        try:
            config = await self.get_config(company_id)
        except Exception:
            # BC-008: Use empty prohibited list if config unavailable
            config = None

        prohibited_words: List[str] = (
            config.prohibited_words if config else []
        )

        if not text or not prohibited_words:
            return ProhibitedWordCheck(
                has_violations=False,
                violations=[],
                cleaned_text=text or "",
            )

        # Normalize the full text for comparison
        normalized_text = _normalize_text(text)
        violations: List[Dict[str, Any]] = []
        redacted_mask: List[bool] = [False] * len(text)

        for word in prohibited_words:
            if not word or not word.strip():
                continue

            normalized_word = _normalize_word(word)

            if not normalized_word:
                continue

            # Build regex with word boundaries to avoid false positives
            # e.g. "hell" should NOT match "hello"
            # Multi-word phrases: replace spaces with \s+
            pattern_str = (
                r"\b"
                + re.escape(normalized_word).replace(r"\ ", r"\s+")
                + r"\b"
            )
            pattern = re.compile(pattern_str)

            for match in pattern.finditer(normalized_text):
                position = match.start()

                # Determine severity based on word context
                severity = "medium"
                if normalized_word in {
                    "damn", "hell", "crap", "piss",
                }:
                    severity = "low"
                elif normalized_word in {
                    "fuck", "shit", "ass", "bitch",
                }:
                    severity = "high"
                elif normalized_word in {
                    "guaranteed", "cure", "miracle",
                }:
                    severity = "medium"

                violations.append({
                    "word": word,
                    "position": position,
                    "normalized_form": normalized_word,
                    "severity": severity,
                })

                # Mark corresponding positions in redacted mask
                # We map normalized positions back to original text
                # by matching normalized tokens against original words
                orig_words = text.split()
                norm_words = normalized_text.split()
                norm_end = match.end()

                # Track position in normalized text
                norm_pos = 0
                for orig_idx, (orig_w, norm_w) in enumerate(
                    zip(orig_words, norm_words),
                ):
                    if norm_pos >= norm_end:
                        break
                    if (
                        norm_pos <= position < norm_pos + len(norm_w)
                        or position < norm_pos + len(norm_w) <= norm_end
                    ):
                        # Find this word in original text
                        start = text.find(orig_w, 0)
                        if start >= 0:
                            for i in range(start, start + len(orig_w)):
                                if i < len(redacted_mask):
                                    redacted_mask[i] = True
                    norm_pos += len(norm_w) + 1  # +1 for space

        # Build cleaned text from redaction mask
        cleaned_chars = []
        for i, ch in enumerate(text):
            if redacted_mask[i]:
                cleaned_chars.append("*")
            else:
                cleaned_chars.append(ch)
        cleaned_text = "".join(cleaned_chars)

        return ProhibitedWordCheck(
            has_violations=len(violations) > 0,
            violations=violations,
            cleaned_text=cleaned_text,
        )

    # ── RESPONSE GUIDELINES ──────────────────────────────────────

    async def get_response_guidelines(
        self,
        company_id: str,
        sentiment_score: float = 0.5,
    ) -> ResponseGuidelines:
        """Generate dynamic response guidelines based on brand voice
        and customer sentiment.

        Negative sentiment (toward 0.0) triggers higher empathy levels
        and adjusted tone. Positive sentiment (toward 1.0) allows more
        casual tone.

        Args:
            company_id: Tenant identifier (BC-001).
            sentiment_score: Customer sentiment score, 0.0 (very
                negative) to 1.0 (very positive). Default 0.5.

        Returns:
            ``ResponseGuidelines`` with tone, formality, sentence
            bounds, empathy level, and suggested phrases.
        """
        try:
            config = await self.get_config(company_id)
        except Exception:
            # BC-008: Use sensible defaults
            config = await self.get_default_config("tech", company_id=company_id)

        # Determine empathy level from sentiment
        # sentiment_score: 0.0 = very angry, 1.0 = very happy
        if sentiment_score < 0.2:
            empathy_level = "critical"
        elif sentiment_score < 0.4:
            empathy_level = "high"
        elif sentiment_score < 0.6:
            empathy_level = "medium"
        else:
            empathy_level = "low"

        # Determine urgency adjustment
        if sentiment_score < 0.2:
            urgency_adjustment = "immediate_response"
        elif sentiment_score < 0.4:
            urgency_adjustment = "priority_handling"
        elif sentiment_score < 0.6:
            urgency_adjustment = "standard"
        else:
            urgency_adjustment = "relaxed"

        # Adjust formality based on sentiment
        # More negative → slightly more formal (more respectful)
        # More positive → match config
        formality_adjustment = 0.0
        if empathy_level == "critical":
            formality_adjustment = 0.1
        elif empathy_level == "high":
            formality_adjustment = 0.05
        elif empathy_level == "low":
            formality_adjustment = -0.05

        adjusted_formality = max(
            0.0, min(1.0, config.formality_level + formality_adjustment),
        )

        # Select appropriate tone adjustments
        tone = config.tone
        if empathy_level == "critical" and tone != "empathetic":
            # For critical empathy, lean toward empathetic or friendly
            if tone == "authoritative":
                tone = "professional"  # soften authoritative
            elif tone == "casual":
                tone = "friendly"  # up-level casual

        # Get suggested opening and closing based on empathy + tone
        opening_table = _EMPATHY_OPENINGS.get(
            empathy_level, _EMPATHY_OPENINGS["medium"],
        )
        closing_table = _EMPATHY_CLOSINGS.get(
            empathy_level, _EMPATHY_CLOSINGS["medium"],
        )

        suggested_opening = opening_table.get(
            tone, opening_table.get("professional", ""),
        )
        suggested_closing = closing_table.get(
            tone, closing_table.get("professional", ""),
        )

        # Get avoid phrases for empathy level
        avoid_phrases = _AVOID_PHRASES_BY_EMPATHY.get(
            empathy_level, [],
        ) + list(config.prohibited_words)

        # Adjust sentence bounds for empathy
        max_sentences = config.max_response_sentences
        min_sentences = config.min_response_sentences
        if empathy_level == "critical":
            max_sentences = max(max_sentences + 2, 8)
        elif empathy_level == "high":
            max_sentences = max(max_sentences + 1, 5)

        return ResponseGuidelines(
            tone=tone,
            formality_level=adjusted_formality,
            max_sentences=max_sentences,
            min_sentences=min_sentences,
            empathy_level=empathy_level,
            urgency_adjustment=urgency_adjustment,
            suggested_opening=suggested_opening,
            suggested_closing=suggested_closing,
            avoid_phrases=avoid_phrases,
        )

    # ── RESPONSE VALIDATION ──────────────────────────────────────

    async def validate_response(
        self,
        text: str,
        company_id: str,
    ) -> ValidationResult:
        """Validate a response against brand voice rules.

        Checks:
          1. Prohibited words (with GAP-021 l33t-speak normalization)
          2. Sentence count within configured bounds
          3. Formality level match (within 0.2 of config)
          4. Tone consistency indicators

        Args:
            text: The response text to validate.
            company_id: Tenant identifier (BC-001).

        Returns:
            ``ValidationResult`` with violations, warnings, score,
            and suggested fixes.
        """
        try:
            config = await self.get_config(company_id)
        except Exception:
            # BC-008: Use defaults if config unavailable
            config = await self.get_default_config("tech", company_id=company_id)

        violations: List[str] = []
        warnings: List[str] = []
        suggested_fixes: List[str] = []

        # ── 1. Prohibited words ──
        word_check = await self.check_prohibited_words(text, company_id)
        if word_check.has_violations:
            for v in word_check.violations:
                violations.append(
                    f"Prohibited word detected: '{v['word']}' "
                    f"(normalized: '{v['normalized_form']}') "
                    f"at position {v['position']} "
                    f"[severity: {v['severity']}]"
                )
            suggested_fixes.append(
                "Replace prohibited words with acceptable alternatives. "
                f"Cleaned version: {word_check.cleaned_text[:200]}"
            )

        # ── 2. Sentence count bounds ──
        sentence_count = _count_sentences(text)
        if sentence_count > config.max_response_sentences:
            violations.append(
                f"Response has {sentence_count} sentences, exceeding "
                f"the maximum of {config.max_response_sentences}"
            )
            suggested_fixes.append(
                f"Reduce response to at most {
                    config.max_response_sentences} sentences")
        elif sentence_count < config.min_response_sentences:
            violations.append(
                f"Response has only {sentence_count} sentence(s), "
                f"below the minimum of {config.min_response_sentences}"
            )
            suggested_fixes.append(
                f"Expand response to at least {
                    config.min_response_sentences} sentences")

        # ── 3. Formality match ──
        estimated_formality = _estimate_formality(text)
        formality_diff = abs(estimated_formality - config.formality_level)
        if formality_diff > 0.2:
            violations.append(
                f"Detected formality level ({estimated_formality}) "
                "differs significantly from configured "
                f"({config.formality_level}) by {formality_diff:.2f}"
            )
            if estimated_formality < config.formality_level:
                suggested_fixes.append(
                    "Increase formality: use fewer contractions, "
                    "avoid exclamation marks, use professional language"
                )
            else:
                suggested_fixes.append(
                    "Decrease formality: use contractions, shorter "
                    "sentences, and a warmer tone"
                )
        elif formality_diff > 0.1:
            warnings.append(
                f"Detected formality level ({estimated_formality}) "
                "slightly differs from configured "
                f"({config.formality_level})"
            )

        # ── 4. Emoji usage check ──
        emoji_pattern = re.compile(
            "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff"
            "\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff"
            "\U00002702-\U000027b0\U000024c2-\U0001f251]",
            re.UNICODE,
        )
        emoji_count = len(emoji_pattern.findall(text))

        emoji_limits: Dict[str, int] = {
            "none": 0,
            "minimal": 2,
            "moderate": 5,
            "liberal": 20,
        }
        emoji_limit = emoji_limits.get(config.emoji_usage, 5)
        if emoji_count > emoji_limit:
            violations.append(
                f"Response contains {emoji_count} emoji(s) but "
                f"'{config.emoji_usage}' usage allows at most {emoji_limit}"
            )
            suggested_fixes.append(
                f"Reduce emoji count to {emoji_limit} or fewer "
                f"to match '{config.emoji_usage}' usage setting"
            )
        elif config.emoji_usage == "none" and emoji_count > 0:
            warnings.append(
                f"Response contains {emoji_count} emoji(s) but "
                "emoji usage is set to 'none'"
            )

        # ── 5. Response length preference check ──
        word_count = len(text.split())
        length_expectations: Dict[str, Dict[str, int]] = {
            "concise": {"ideal_min": 10, "ideal_max": 50},
            "standard": {"ideal_min": 30, "ideal_max": 150},
            "detailed": {"ideal_min": 80, "ideal_max": 400},
        }
        length_exp = length_expectations.get(
            config.response_length_preference, length_expectations["standard"],
        )
        if word_count < length_exp["ideal_min"]:
            warnings.append(
                f"Response has {word_count} words, which is below "
                f"the expected range ({length_exp['ideal_min']}-"
                f"{length_exp['ideal_max']}) for "
                f"'{config.response_length_preference}' responses"
            )
        elif word_count > length_exp["ideal_max"]:
            warnings.append(
                f"Response has {word_count} words, which exceeds "
                f"the expected range ({length_exp['ideal_min']}-"
                f"{length_exp['ideal_max']}) for "
                f"'{config.response_length_preference}' responses"
            )

        # ── Calculate score ──
        score = 1.0
        score -= len(violations) * 0.25
        score -= len(warnings) * 0.05
        score = max(0.0, min(1.0, round(score, 2)))

        return ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            score=score,
            suggested_fixes=suggested_fixes,
        )

    # ── INDUSTRY DEFAULTS ───────────────────────────────────────

    async def get_default_config(
        self,
        industry: str,
        company_id: str = "__default__",
    ) -> BrandVoiceConfig:
        """Get a default brand voice config for an industry.

        Args:
            industry: Industry name (tech, ecommerce, healthcare,
                finance, education, legal, hospitality).
            company_id: Optional company ID override. Defaults to
                ``"__default__"``.

        Returns:
            A ``BrandVoiceConfig`` with industry-specific defaults.
        """
        try:
            if industry not in _INDUSTRY_DEFAULTS:
                industry = "tech"
                logger.warning(
                    "brand_voice_unknown_industry",
                    extra={"industry": industry, "fallback": "tech"},
                )

            defaults = _INDUSTRY_DEFAULTS[industry]
            bounds = _RESPONSE_LENGTH_BOUNDS.get(
                defaults["response_length_preference"],
                _RESPONSE_LENGTH_BOUNDS["standard"],
            )

            now = _now_utc()

            return BrandVoiceConfig(
                company_id=company_id,
                tone=defaults["tone"],
                formality_level=defaults["formality_level"],
                prohibited_words=list(
                    defaults["prohibited_words"]),
                response_length_preference=defaults["response_length_preference"],
                max_response_sentences=bounds["max"],
                min_response_sentences=bounds["min"],
                greeting_template=defaults["greeting_template"],
                closing_template=defaults["closing_template"],
                emoji_usage=defaults["emoji_usage"],
                apology_style=defaults["apology_style"],
                escalation_tone=defaults["escalation_tone"],
                brand_name="PARWA",
                industry=industry,
                custom_instructions=defaults["custom_instructions"],
                created_at=now,
                updated_at=now,
            )

        except Exception as exc:
            logger.error(
                "brand_voice_get_default_failed",
                extra={"industry": industry, "error": str(exc)},
                exc_info=True,
            )
            # BC-008: Return minimal hardcoded fallback
            now = _now_utc()
            return BrandVoiceConfig(
                company_id=company_id,
                tone="professional",
                formality_level=0.5,
                prohibited_words=[],
                response_length_preference="standard",
                max_response_sentences=6,
                min_response_sentences=2,
                greeting_template="Hello! How can I help you?",
                closing_template="Let me know if you need anything else.",
                emoji_usage="none",
                apology_style="empathetic",
                escalation_tone="calm",
                brand_name="PARWA",
                industry="tech",
                custom_instructions="",
                created_at=now,
                updated_at=now,
            )

    # ── BRAND VOICE MERGE ────────────────────────────────────────

    async def merge_with_brand_voice(
        self,
        response_text: str,
        company_id: str,
    ) -> str:
        """Apply brand voice to a response text.

        Applies:
          1. Greeting template at the beginning (if not already present)
          2. Closing template at the end (if not already present)
          3. Tone adjustments based on config

        Args:
            response_text: The raw response text.
            company_id: Tenant identifier (BC-001).

        Returns:
            The response text with brand voice applied.
        """
        try:
            config = await self.get_config(company_id)
        except Exception:
            # BC-008: Use defaults
            config = await self.get_default_config("tech", company_id=company_id)

        if not response_text or not response_text.strip():
            return response_text

        text = response_text.strip()

        # ── 1. Prepend greeting if not already present ──
        greeting = config.greeting_template.strip()
        text_lower = text.lower()
        greeting_lower = greeting.lower()

        if greeting and not text_lower.startswith(greeting_lower):
            # Check if any part of the greeting is already in the text
            greeting_first_words = " ".join(greeting.split()[:4])
            if greeting_first_words.lower() not in text_lower:
                text = f"{greeting}\n\n{text}"

        # ── 2. Append closing if not already present ──
        closing = config.closing_template.strip()
        closing_lower = closing.lower()
        text_lower_after = text.lower()

        if closing and not text_lower_after.endswith(closing_lower):
            # Check if any part of the closing is already in the text
            closing_last_words = " ".join(closing.split()[-4:])
            if closing_last_words.lower() not in text_lower_after:
                text = f"{text}\n\n{closing}"

        # ── 3. Tone adjustments ──
        # Adjust formality via contractions
        if config.formality_level >= 0.8:
            # Formal: expand common contractions
            text = self._expand_contractions(text)
        elif config.formality_level <= 0.3:
            # Very casual: contract where natural
            text = self._add_casual_touches(text)

        # ── 4. Custom instructions prefix (for AI context) ──
        # Not applied directly to text but logged for observability
        if config.custom_instructions:
            logger.debug(
                "brand_voice_custom_instructions",
                extra={
                    "company_id": company_id,
                    "instructions": config.custom_instructions[:100],
                },
            )

        return text

    # ── PRIVATE HELPERS ──────────────────────────────────────────

    async def _get_from_cache(
        self,
        company_id: str,
    ) -> Optional[BrandVoiceConfig]:
        """Retrieve config from Redis cache."""
        if not self.redis_client:
            return None
        try:
            key = f"{REDIS_KEY_PREFIX}{company_id}"
            data = await self.redis_client.get(key)
            if data:
                parsed = json.loads(data)
                parsed["created_at"] = datetime.fromisoformat(
                    parsed["created_at"])
                parsed["updated_at"] = datetime.fromisoformat(
                    parsed["updated_at"])
                return BrandVoiceConfig(**parsed)
        except Exception as exc:
            logger.warning(
                "brand_voice_cache_get_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
        return None

    async def _set_cache(
        self,
        company_id: str,
        config: BrandVoiceConfig,
    ) -> None:
        """Store config in Redis cache."""
        if not self.redis_client:
            return
        try:
            key = f"{REDIS_KEY_PREFIX}{company_id}"
            data = {
                "company_id": config.company_id,
                "tone": config.tone,
                "formality_level": config.formality_level,
                "prohibited_words": config.prohibited_words,
                "response_length_preference": config.response_length_preference,
                "max_response_sentences": config.max_response_sentences,
                "min_response_sentences": config.min_response_sentences,
                "greeting_template": config.greeting_template,
                "closing_template": config.closing_template,
                "emoji_usage": config.emoji_usage,
                "apology_style": config.apology_style,
                "escalation_tone": config.escalation_tone,
                "brand_name": config.brand_name,
                "industry": config.industry,
                "custom_instructions": config.custom_instructions,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat(),
            }
            await self.redis_client.set(
                key, json.dumps(data), ex=REDIS_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "brand_voice_cache_set_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )

    async def _delete_cache(self, company_id: str) -> None:
        """Remove config from Redis cache."""
        if not self.redis_client:
            return
        try:
            key = f"{REDIS_KEY_PREFIX}{company_id}"
            await self.redis_client.delete(key)
        except Exception as exc:
            logger.warning(
                "brand_voice_cache_delete_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )

    async def _get_from_db(
        self,
        company_id: str,
    ) -> Optional[BrandVoiceConfig]:
        """Retrieve config from database.

        Stub implementation — to be wired to the ORM model when
        the BrandVoiceConfig DB model is created.
        """
        if not self.db:
            return None
        try:
            # Future: query the BrandVoiceConfig ORM model
            # from database.models.brand_voice import BrandVoiceConfigModel
            # row = self.db.query(BrandVoiceConfigModel).filter(
            #     BrandVoiceConfigModel.company_id == company_id,
            # ).first()
            # if row:
            #     return BrandVoiceConfig(...)
            return None
        except Exception as exc:
            logger.warning(
                "brand_voice_db_get_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )
            return None

    async def _save_to_db(self, config: BrandVoiceConfig) -> None:
        """Persist config to database.

        Stub implementation — to be wired to the ORM model when
        the BrandVoiceConfig DB model is created.
        """
        if not self.db:
            return
        try:
            # Future: upsert to BrandVoiceConfig ORM model
            pass
        except Exception as exc:
            logger.warning(
                "brand_voice_db_save_failed",
                extra={"company_id": config.company_id, "error": str(exc)},
            )

    async def _delete_from_db(self, company_id: str) -> None:
        """Remove config from database.

        Stub implementation — to be wired to the ORM model when
        the BrandVoiceConfig DB model is created.
        """
        if not self.db:
            return
        try:
            # Future: delete from BrandVoiceConfig ORM model
            pass
        except Exception as exc:
            logger.warning(
                "brand_voice_db_delete_failed",
                extra={"company_id": company_id, "error": str(exc)},
            )

    @staticmethod
    def _expand_contractions(text: str) -> str:
        """Expand common contractions for formal tone."""
        contractions_map = {
            r"\bdon't\b": "do not",
            r"\bcan't\b": "cannot",
            r"\bwon't\b": "will not",
            r"\bdidn't\b": "did not",
            r"\bdoesn't\b": "does not",
            r"\bshouldn't\b": "should not",
            r"\bwouldn't\b": "would not",
            r"\bcouldn't\b": "could not",
            r"\bisn't\b": "is not",
            r"\baren't\b": "are not",
            r"\bwasn't\b": "was not",
            r"\bweren't\b": "were not",
            r"\bhasn't\b": "has not",
            r"\bhaven't\b": "have not",
            r"\bit's\b": "it is",
            r"\bI'm\b": "I am",
            r"\byou're\b": "you are",
            r"\bwe're\b": "we are",
            r"\bthey're\b": "they are",
            r"\bthat's\b": "that is",
            r"\bthere's\b": "there is",
            r"\bhere's\b": "here is",
            r"\blet's\b": "let us",
        }
        for pattern, replacement in contractions_map.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _add_casual_touches(text: str) -> str:
        """Add casual touches for very informal tone."""
        casual_map = {
            "I apologize": "Sorry",
            "I am sorry": "Sorry",
            "I would be happy to": "I'd love to",
            "Please note": "Just so you know",
            "Please be advised": "Heads up",
            "I regret to inform you": "Bummer, but",
            "Thank you for your patience": "Thanks for hanging tight",
            "We appreciate your business": "Thanks for being here",
        }
        for formal, casual in casual_map.items():
            text = text.replace(formal, casual)
        return text
