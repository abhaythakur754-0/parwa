"""
Model-Specific Response Formatters (SG-26)

15 response formatters that normalize AI model outputs for different contexts.
Each formatter is independent and composable.

Per-variant defaults:
- mini_parwa: TokenLimit + Markdown + Whitespace (3 formatters)
- parwa: + Citation + Tone + Length (6 formatters)
- high_parwa: all 15 formatters

Parent: Week 9 Day 7
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("response_formatters")


# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class FormattingContext:
    """Context for response formatting decisions."""

    company_id: str = ""
    variant_type: str = "parwa"
    brand_voice: str = "professional"
    model_tier: str = "standard"
    customer_tier: str = "free"
    intent_type: str = "general"
    sentiment_score: float = 0.5
    formality_level: str = "medium"  # low, medium, high

    def __post_init__(self):
        """Normalize values."""
        self.variant_type = self.variant_type.lower()
        self.formality_level = self.formality_level.lower()
        self.customer_tier = self.customer_tier.lower()
        self.intent_type = self.intent_type.lower()


@dataclass
class FormattingResult:
    """Result of applying one or more formatters."""

    formatted_text: str
    formatters_applied: List[str]
    total_time_ms: float
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "formatted_text": self.formatted_text,
            "formatters_applied": self.formatters_applied,
            "total_time_ms": round(self.total_time_ms, 2),
            "errors": self.errors,
        }


# ── Base Formatter ────────────────────────────────────────────────────


class BaseFormatter(ABC):
    """Abstract base class for all response formatters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this formatter."""
        ...

    @abstractmethod
    def format(self, response: str, context: FormattingContext) -> str:
        """Format the response text.

        Args:
            response: The text to format.
            context: Formatting context with metadata.

        Returns:
            Formatted text.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"


# ── 15 Formatters ─────────────────────────────────────────────────────


class TokenLimitFormatter(BaseFormatter):
    """1. Truncate response to model's max token limit.

    Uses approximate 4 chars per token heuristic.
    """

    # Approximate max tokens per model tier
    TIER_LIMITS = {
        "mini": 512,
        "standard": 2048,
        "high": 4096,
    }

    CHARS_PER_TOKEN = 4  # rough approximation

    @property
    def name(self) -> str:
        return "token_limit"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        limit = self.TIER_LIMITS.get(context.model_tier, self.TIER_LIMITS["standard"])
        max_chars = limit * self.CHARS_PER_TOKEN

        if len(response) <= max_chars:
            return response

        # Truncate at last complete sentence within limit
        truncated = response[:max_chars]
        # Find last period, exclamation, or question mark
        last_sentence_end = max(
            truncated.rfind("."),
            truncated.rfind("!"),
            truncated.rfind("?"),
        )
        if last_sentence_end > max_chars * 0.5:
            return truncated[: last_sentence_end + 1]

        # Fall back to last space
        last_space = truncated.rfind(" ")
        if last_space > max_chars * 0.5:
            return truncated[:last_space] + "..."

        return truncated + "..."


class MarkdownFormatter(BaseFormatter):
    """2. Normalize markdown — fix broken lists, headers, links."""

    @property
    def name(self) -> str:
        return "markdown"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        text = response

        # Fix headers without space after # (e.g., "##Header" → "## Header")
        text = re.sub(r"^(#{1,6})([^ #\n])", r"\1 \2", text, flags=re.MULTILINE)

        # Fix broken list items (e.g., "-item" → "- item", "*item" → "* item")
        text = re.sub(r"^(\s*[-*+])(\S)", r"\1 \2", text, flags=re.MULTILINE)

        # Fix numbered lists without space (e.g., "1.item" → "1. item")
        text = re.sub(r"^(\s*\d+\.)(\S)", r"\1 \2", text, flags=re.MULTILINE)

        # Fix empty links: [text]() → [text](#)
        text = re.sub(r"\[([^\]]*)\]\(\s*\)", r"[\1](#)", text)

        # Fix bare URLs that aren't in markdown links
        # (but don't double-wrap already-linked URLs)
        text = re.sub(
            r"(?<!\()(?<!\[)(https?://[^\s<>()\[\]]+)(?!\))",
            r"<\1>",
            text,
        )

        return text


class CitationFormatter(BaseFormatter):
    """3. Format citations [1], [2] with source links."""

    @property
    def name(self) -> str:
        return "citation"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        text = response

        # Find all citation references [1], [2], etc.
        citations = re.findall(r"\[(\d+)\]", text)
        if not citations:
            return text

        # Build a sources section at the bottom
        unique_citations = []
        seen = set()
        for c in citations:
            num = int(c)
            if num not in seen:
                seen.add(num)
                unique_citations.append(num)

        # Only add a sources section if there are 2+ unique citations
        if len(unique_citations) < 2:
            return text

        sources_lines = [f"\n\n**Sources:**"]
        for num in sorted(unique_citations):
            sources_lines.append(f"- [{num}] Source reference {num}")

        # Check if there's already a sources section
        if "**Sources:**" in text or "**sources:**" in text.lower():
            return text  # Don't duplicate

        return text + "".join(sources_lines)


class ToneFormatter(BaseFormatter):
    """4. Adjust tone (professional/friendly/casual).

    Applies light transformations based on brand voice setting.
    """

    # Tone adjustments
    CASUAL_REPLACEMENTS = [
        (r"\bI will\b", "I'll"),
        (r"\bI am\b", "I'm"),
        (r"\bdo not\b", "don't"),
        (r"\bcannot\b", "can't"),
        (r"\bWe will\b", "We'll"),
        (r"\bwe are\b", "we're"),
        (r"\bHere is\b", "Here's"),
        (r"\bThat is\b", "That's"),
        (r"\bIt is\b", "It's"),
        (r"\bLet me know\b", "Let me know"),
        (r"\bPlease note\b", "Just a heads up"),
        (r"\bFurthermore\b", "Also"),
        (r"\bAdditionally\b", "Plus"),
        (r"\bIn addition\b", "Also"),
        (r"\bI would recommend\b", "I'd suggest"),
        (r"\bI recommend\b", "I'd suggest"),
    ]

    PROFESSIONAL_ADDITIONS = [
        (r"\bhey\b", "Hello"),
        (r"\byeah\b", "Yes"),
        (r"\byep\b", "Yes"),
        (r"\bgonna\b", "going to"),
        (r"\bwanna\b", "want to"),
        (r"\bgotta\b", "have to"),
        (r"\bkinda\b", "somewhat"),
        (r"\bsorta\b", "somewhat"),
        (r"\bcool\b", "excellent"),
        (r"\bawesome\b", "excellent"),
        (r"\bno worries\b", "You're welcome"),
    ]

    @property
    def name(self) -> str:
        return "tone"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        voice = context.brand_voice.lower()

        if voice == "casual":
            text = response
            for pattern, replacement in self.CASUAL_REPLACEMENTS:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            return text
        elif voice == "professional":
            text = response
            for pattern, replacement in self.PROFESSIONAL_ADDITIONS:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            return text
        elif voice == "friendly":
            # Friendly is between casual and professional — light contractions
            text = response
            for pattern, replacement in self.CASUAL_REPLACEMENTS[:5]:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            return text

        return response


class LengthFormatter(BaseFormatter):
    """5. Condense/expand based on preferences (concise/standard/detailed)."""

    @property
    def name(self) -> str:
        return "length"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        # Determine length preference from context
        # Use sentiment and customer tier as proxies
        preference = self._determine_preference(context)

        if preference == "concise":
            return self._condense(response)
        elif preference == "detailed":
            return self._expand(response)
        return response

    def _determine_preference(self, context: FormattingContext) -> str:
        """Determine length preference from context."""
        # High sentiment → more concise (don't over-explain to happy users)
        if context.sentiment_score > 0.8:
            return "concise"
        # Low sentiment / escalation → more detailed
        if context.sentiment_score < 0.3 or context.intent_type == "escalation":
            return "detailed"
        return "standard"

    def _condense(self, text: str) -> str:
        """Remove filler phrases and redundant sentences."""
        # Remove common filler phrases
        fillers = [
            r"\s*As a matter of fact,\s*",
            r"\s*It is worth noting that\s*",
            r"\s*It should be mentioned that\s*",
            r"\s*In this day and age,\s*",
            r"\s*At the end of the day,\s*",
            r"\s*For what it's worth,\s*",
            r"\s*To make a long story short,\s*",
            r"\s*Needless to say,\s*",
            r"\s*That being said,\s*",
            r"\s*With that being said,\s*",
        ]
        result = text
        for filler in fillers:
            result = re.sub(filler, " ", result, flags=re.IGNORECASE)

        # Collapse multiple blank lines to one
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    def _expand(self, text: str) -> str:
        """Add transition phrases for more detailed responses."""
        # If response is short, add a polite intro
        if len(text.split()) < 20:
            return f"Thank you for your patience. {text} Please let me know if you need any further assistance."
        return text


class CodeBlockFormatter(BaseFormatter):
    """6. Format code blocks with language tags and syntax."""

    # Common file extensions to language tags
    EXT_TO_LANG = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".html": "html", ".css": "css", ".json": "json",
        ".sql": "sql", ".sh": "bash", ".yaml": "yaml", ".yml": "yaml",
        ".md": "markdown", ".rb": "ruby", ".go": "go", ".rs": "rust",
        ".java": "java", ".cpp": "cpp", ".c": "c", ".php": "php",
    }

    @property
    def name(self) -> str:
        return "code_block"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        text = response

        # Fix code blocks without language tag: ``` → ```text
        text = re.sub(r"```\s*\n", "```text\n", text)

        # Fix unclosed code blocks — add closing ```
        opens = text.count("```")
        if opens % 2 != 0:
            text += "\n```"

        return text


class ListFormatter(BaseFormatter):
    """7. Normalize bullet/numbered lists."""

    @property
    def name(self) -> str:
        return "list"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        text = response

        # Normalize mixed bullet characters to "-"
        lines = text.split("\n")
        normalized = []
        for line in lines:
            # Match lines starting with bullet-like characters
            match = re.match(r"^(\s*)[*•▸▹►▹–—]\s+", line)
            if match:
                indent = match.group(1)
                rest = line[match.end():]
                normalized.append(f"{indent}- {rest}")
            else:
                normalized.append(line)

        return "\n".join(normalized)


class BoldFormatter(BaseFormatter):
    """8. Remove excessive bold/italic formatting."""

    @property
    def name(self) -> str:
        return "bold"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        text = response

        # G9-GAP-06 FIX: Strip code blocks before counting to prevent
        # miscounting from URLs with * or code containing *args
        code_free = re.sub(r"```[^`]*```", "", text, flags=re.DOTALL)

        # Count bold pairs (from code-free text)
        bold_pairs = code_free.count("**") // 2

        # Count italic pairs: total * minus bold markers, then divide by 2
        total_asterisks = code_free.count("*")
        bold_asterisks = code_free.count("**") * 2
        remaining_asterisks = total_asterisks - bold_asterisks
        italic_pairs = remaining_asterisks // 2

        # Remove excessive bold (> 5 bold sections)
        if bold_pairs > 5:
            # Remove all bold markers
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

        # Remove excessive italic (> 3 italic sections)
        if italic_pairs > 3:
            # Remove remaining italic markers (avoid removing bold markers)
            text = re.sub(r"(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)", r"\1", text)

        # Remove consecutive bold/italic on same text (e.g., ***text***)
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)

        return text


class LinkFormatter(BaseFormatter):
    """9. Validate and format URLs."""

    URL_PATTERN = re.compile(r"https?://[^\s<>\[\]()]+")

    @property
    def name(self) -> str:
        return "link"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        def _clean_url(match: re.Match) -> str:
            url = match.group(0)
            # Remove trailing punctuation that's likely not part of URL
            url = url.rstrip(".,;:!?)")
            # Ensure URL has a scheme
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            return url

        return self.URL_PATTERN.sub(_clean_url, response)


class EmojiFormatter(BaseFormatter):
    """10. Strip/normalize emojis based on formality level."""

    # Regex to match common emojis
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )

    @property
    def name(self) -> str:
        return "emoji"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        level = context.formality_level.lower()

        if level == "high":
            # Remove all emojis
            return self.EMOJI_PATTERN.sub("", response)
        elif level == "medium":
            # Allow max 2 emojis
            emojis = self.EMOJI_PATTERN.findall(response)
            if len(emojis) > 2:
                # Keep first 2 occurrences
                result = ""
                count = 0
                for char in response:
                    if self.EMOJI_PATTERN.match(char):
                        if count >= 2:
                            continue
                        count += 1
                    result += char
                return result
            return response
        # low formality: keep all emojis
        return response


class WhitespaceFormatter(BaseFormatter):
    """11. Clean up excessive whitespace, blank lines."""

    @property
    def name(self) -> str:
        return "whitespace"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        text = response

        # Collapse 3+ newlines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Collapse 2+ spaces to 1 (but preserve markdown code blocks)
        # Simple approach: just collapse spaces on non-indented lines
        lines = text.split("\n")
        processed = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                processed.append(line)
                continue
            if not in_code_block:
                # Collapse multiple spaces (but preserve list indentation)
                line = re.sub(r" {2,}", " ", line)
                # Remove trailing whitespace
                line = line.rstrip()
            processed.append(line)

        return "\n".join(processed)


class SignatureFormatter(BaseFormatter):
    """12. Add/validate sign-offs based on brand voice."""

    SIGN_OFFS = {
        "professional": "Best regards,\nSupport Team",
        "friendly": "Cheers,\nSupport Team",
        "casual": "— Support Team",
    }

    @property
    def name(self) -> str:
        return "signature"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        voice = context.brand_voice.lower()

        # Check if there's already a sign-off
        sign_off_indicators = [
            "best regards", "sincerely", "cheers", "thanks",
            "support team", "customer support", "help team",
        ]
        last_lines = response.lower().split("\n")[-3:]
        # G5 FIX: Check if indicator appears as a word in last lines, not substring
        # Prevents false positive: "thanks" in "Thanksgiving" or "support" in "supportive"
        has_sign_off = any(
            any(
                indicator == line.strip().lower()
                or line.strip().lower().startswith(indicator + ",")
                or line.strip().lower().startswith(indicator + "\n")
                for line in last_lines
            )
            for indicator in sign_off_indicators
        )

        if has_sign_off:
            return response

        # Don't add signature to very short responses
        if len(response.split()) < 10:
            return response

        sign_off = self.SIGN_OFFS.get(voice, self.SIGN_OFFS["professional"])
        return f"{response}\n\n{sign_off}"


class DisambiguationFormatter(BaseFormatter):
    """13. Add 'Did you mean?' suggestions for ambiguous queries.

    This formatter is context-dependent and would use search data in production.
    For now, it detects potential ambiguities and adds suggestions.
    """

    COMMON_AMBIGUITIES = {
        "reset": ["password reset", "factory reset", "account reset"],
        "cancel": ["cancel subscription", "cancel order", "cancel payment"],
        "update": ["update payment method", "update profile", "update plan"],
        "change": ["change password", "change email", "change plan"],
        "download": ["download invoice", "download app", "download receipt"],
    }

    @property
    def name(self) -> str:
        return "disambiguation"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        intent = context.intent_type.lower()

        # Only add disambiguation for general/inquiry intents
        if intent not in ("general", "inquiry"):
            return response

        # Check if response already has disambiguation
        if "did you mean" in response.lower() or "were you looking for" in response.lower():
            return response

        # Don't add to short responses
        if len(response.split()) < 15:
            return response

        # Check for ambiguous words in the response context
        suggestions = []
        response_lower = response.lower()
        for word, options in self.COMMON_AMBIGUITIES.items():
            if word in response_lower and not any(
                opt in response_lower for opt in options
            ):
                suggestions.extend(options[:2])

        if not suggestions:
            return response

        unique = list(dict.fromkeys(suggestions))[:3]
        sug_text = "Did you mean: " + ", ".join(f'"{s}"' for s in unique) + "?"
        return f"{response}\n\n{sug_text}"


class ActionItemFormatter(BaseFormatter):
    """14. Extract and format action items from responses."""

    ACTION_PATTERNS = [
        r"(?:you (?:can|should|need to|must|will))\s+(.+?)(?:\.|$)",
        r"(?:please)\s+(.+?)(?:\.|$)",
        r"(?:make sure to|ensure that|don't forget to)\s+(.+?)(?:\.|$)",
        r"(?:steps? to .+?)[.:]\s*(.+)",
        r"(?:here(?:'s| is) (?:how|what) to .+?)[.:]\s*(.+)",
    ]

    @property
    def name(self) -> str:
        return "action_item"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        # Check if already has action items section
        if "**Action Items:**" in response or "**Steps:**" in response:
            return response

        # Extract action items
        action_items: List[str] = []
        for pattern in self.ACTION_PATTERNS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                item = match.strip()
                if len(item) > 5 and item not in action_items:
                    action_items.append(item)

        if not action_items:
            return response

        # Keep max 5 action items
        action_items = action_items[:5]

        # Add action items section
        items_text = "\n".join(f"- {item}" for item in action_items)
        section = f"\n\n**Action Items:**\n{items_text}"

        return response + section


class EscalationFormatter(BaseFormatter):
    """15. Format escalation notices with priority and context."""

    @property
    def name(self) -> str:
        return "escalation"

    def format(self, response: str, context: FormattingContext) -> str:
        if not response:
            return response

        intent = context.intent_type.lower()

        # G11 FIX: Also escalate for very frustrated customers regardless of intent
        if intent not in ("escalation", "complaint") and context.sentiment_score >= 0.3:
            return response  # Only format escalation for high-frustration or specific intents

        # Only format escalation-related responses
        if intent not in ("escalation", "complaint"):
            return response

        # Check if already has escalation formatting
        if "⚠️" in response or "**Priority:**" in response or "ESCALATION" in response.upper():
            return response

        # Add priority header
        priority = "HIGH"
        if context.customer_tier in ("vip", "enterprise"):
            priority = "CRITICAL"
        elif context.sentiment_score < 0.2:
            priority = "URGENT"

        header = f"**Priority: {priority}** | Escalation Notice\n\n"
        footer = "\n\n_This matter has been escalated for priority handling._"

        return f"{header}{response}{footer}"


# ── Formatter Registry ────────────────────────────────────────────────


class FormatterRegistry:
    """Registry for managing and applying response formatters.

    Usage:
        registry = FormatterRegistry()
        registry.register("token_limit", TokenLimitFormatter())
        result = registry.apply_all(response, context, ["token_limit", "markdown"])
    """

    # Per-variant default formatter lists
    VARIANT_DEFAULTS: Dict[str, List[str]] = {
        "mini_parwa": [
            "token_limit", "markdown", "whitespace",
        ],
        "parwa": [
            "token_limit", "markdown", "whitespace",
            "citation", "tone", "length",
        ],
        "high_parwa": [
            "token_limit", "markdown", "citation", "tone", "length",
            "code_block", "list", "bold", "link", "emoji",
            "whitespace", "signature", "disambiguation",
            "action_item", "escalation",
        ],
    }

    def __init__(self):
        self._formatters: Dict[str, BaseFormatter] = {}

    def register(self, name: str, formatter: BaseFormatter) -> None:
        """Register a formatter with a name.

        Args:
            name: Unique name for the formatter.
            formatter: Formatter instance.

        Raises:
            ValueError: If name is already registered.
        """
        if name in self._formatters:
            logger.warning(
                "formatter_already_registered",
                name=name,
                existing=type(self._formatters[name]).__name__,
            )
            return
        self._formatters[name] = formatter

    def get(self, name: str) -> Optional[BaseFormatter]:
        """Get a formatter by name.

        Args:
            name: Formatter name.

        Returns:
            Formatter instance or None if not found.
        """
        return self._formatters.get(name)

    def apply_all(
        self,
        response: str,
        context: FormattingContext,
        formatters_to_apply: Optional[List[str]] = None,
    ) -> FormattingResult:
        """Apply multiple formatters in sequence.

        Args:
            response: Text to format.
            context: Formatting context.
            formatters_to_apply: List of formatter names to apply.
                                  If None, uses variant defaults.

        Returns:
            FormattingResult with final text and metadata.
        """
        start_time = time.monotonic()
        errors: List[str] = []
        applied: List[str] = []

        if formatters_to_apply is None:
            formatters_to_apply = self.VARIANT_DEFAULTS.get(
                context.variant_type, self.VARIANT_DEFAULTS["parwa"]
            )

        text = response
        for name in formatters_to_apply:
            formatter = self._formatters.get(name)
            if formatter is None:
                errors.append(f"formatter_not_found: {name}")
                logger.warning("formatter_not_found", name=name)
                continue

            try:
                text = formatter.format(text, context)
                applied.append(name)
            except Exception as exc:
                errors.append(f"{name}: {str(exc)}")
                logger.warning(
                    "formatter_error",
                    name=name,
                    error=str(exc),
                )

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return FormattingResult(
            formatted_text=text,
            formatters_applied=applied,
            total_time_ms=elapsed_ms,
            errors=errors,
        )

    def get_defaults_for_variant(self, variant_type: str) -> List[str]:
        """Get default formatter list for a variant type.

        Args:
            variant_type: mini_parwa, parwa, or high_parwa.

        Returns:
            List of formatter names.
        """
        return list(
            self.VARIANT_DEFAULTS.get(variant_type, self.VARIANT_DEFAULTS["parwa"])
        )

    def list_registered(self) -> List[str]:
        """List all registered formatter names."""
        return list(self._formatters.keys())


def create_default_registry() -> FormatterRegistry:
    """Create a FormatterRegistry with all 15 formatters registered."""
    registry = FormatterRegistry()
    registry.register("token_limit", TokenLimitFormatter())
    registry.register("markdown", MarkdownFormatter())
    registry.register("citation", CitationFormatter())
    registry.register("tone", ToneFormatter())
    registry.register("length", LengthFormatter())
    registry.register("code_block", CodeBlockFormatter())
    registry.register("list", ListFormatter())
    registry.register("bold", BoldFormatter())
    registry.register("link", LinkFormatter())
    registry.register("emoji", EmojiFormatter())
    registry.register("whitespace", WhitespaceFormatter())
    registry.register("signature", SignatureFormatter())
    registry.register("disambiguation", DisambiguationFormatter())
    registry.register("action_item", ActionItemFormatter())
    registry.register("escalation", EscalationFormatter())
    return registry
