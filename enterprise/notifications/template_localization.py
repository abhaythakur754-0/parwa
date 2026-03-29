# Template Localization - Week 48 Builder 4
# Multi-language support for notification templates

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json
import uuid


class LocaleType(Enum):
    LANGUAGE = "language"
    REGION = "region"
    CULTURE = "culture"


@dataclass
class Locale:
    code: str  # e.g., "en-US", "fr-FR"
    language: str  # e.g., "en", "fr"
    region: Optional[str] = None  # e.g., "US", "FR"
    name: str = ""  # e.g., "English (US)"
    native_name: str = ""  # e.g., "English"
    rtl: bool = False  # Right-to-left
    date_format: str = "%m/%d/%Y"
    time_format: str = "%I:%M %p"
    currency_symbol: str = "$"
    decimal_separator: str = "."
    thousands_separator: str = ","


@dataclass
class LocalizedTemplate:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_id: str = ""
    locale_code: str = "en-US"
    subject: Optional[str] = None
    content: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Translation:
    key: str = ""
    locale_code: str = ""
    value: str = ""
    context: Optional[str] = None


class LocalizationManager:
    """Manages template localization and translations"""

    def __init__(self):
        self._locales: Dict[str, Locale] = {}
        self._localized_templates: Dict[str, LocalizedTemplate] = {}
        self._translations: Dict[str, Dict[str, str]] = {}  # key -> {locale -> value}
        self._fallback_locale = "en-US"
        self._register_default_locales()

    def _register_default_locales(self) -> None:
        """Register default locales"""
        defaults = [
            Locale(
                code="en-US",
                language="en",
                region="US",
                name="English (US)",
                native_name="English",
                date_format="%m/%d/%Y",
                time_format="%I:%M %p",
                currency_symbol="$"
            ),
            Locale(
                code="en-GB",
                language="en",
                region="GB",
                name="English (UK)",
                native_name="English",
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                currency_symbol="£"
            ),
            Locale(
                code="es-ES",
                language="es",
                region="ES",
                name="Spanish (Spain)",
                native_name="Español",
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                currency_symbol="€"
            ),
            Locale(
                code="fr-FR",
                language="fr",
                region="FR",
                name="French (France)",
                native_name="Français",
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                currency_symbol="€"
            ),
            Locale(
                code="de-DE",
                language="de",
                region="DE",
                name="German (Germany)",
                native_name="Deutsch",
                date_format="%d.%m.%Y",
                time_format="%H:%M",
                currency_symbol="€",
                decimal_separator=",",
                thousands_separator="."
            ),
            Locale(
                code="ja-JP",
                language="ja",
                region="JP",
                name="Japanese",
                native_name="日本語",
                date_format="%Y/%m/%d",
                time_format="%H:%M",
                currency_symbol="¥"
            ),
            Locale(
                code="zh-CN",
                language="zh",
                region="CN",
                name="Chinese (Simplified)",
                native_name="简体中文",
                date_format="%Y-%m-%d",
                time_format="%H:%M",
                currency_symbol="¥"
            ),
            Locale(
                code="ar-SA",
                language="ar",
                region="SA",
                name="Arabic (Saudi Arabia)",
                native_name="العربية",
                rtl=True,
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                currency_symbol="ر.س"
            ),
            Locale(
                code="hi-IN",
                language="hi",
                region="IN",
                name="Hindi (India)",
                native_name="हिन्दी",
                date_format="%d/%m/%Y",
                time_format="%I:%M %p",
                currency_symbol="₹"
            ),
            Locale(
                code="pt-BR",
                language="pt",
                region="BR",
                name="Portuguese (Brazil)",
                native_name="Português",
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                currency_symbol="R$"
            )
        ]

        for locale in defaults:
            self._locales[locale.code] = locale

    def register_locale(self, locale: Locale) -> None:
        """Register a locale"""
        self._locales[locale.code] = locale

    def get_locale(self, code: str) -> Optional[Locale]:
        """Get locale by code"""
        return self._locales.get(code)

    def get_all_locales(self) -> List[Locale]:
        """Get all registered locales"""
        return list(self._locales.values())

    def get_locales_by_language(self, language: str) -> List[Locale]:
        """Get all locales for a language"""
        return [l for l in self._locales.values() if l.language == language]

    def create_localized_template(
        self,
        template_id: str,
        locale_code: str,
        content: str,
        subject: Optional[str] = None
    ) -> LocalizedTemplate:
        """Create a localized version of a template"""
        localized = LocalizedTemplate(
            template_id=template_id,
            locale_code=locale_code,
            subject=subject,
            content=content
        )

        key = f"{template_id}:{locale_code}"
        self._localized_templates[key] = localized

        return localized

    def get_localized_template(
        self,
        template_id: str,
        locale_code: str
    ) -> Optional[LocalizedTemplate]:
        """Get localized template by template ID and locale"""
        key = f"{template_id}:{locale_code}"
        return self._localized_templates.get(key)

    def get_best_template(
        self,
        template_id: str,
        preferred_locales: List[str]
    ) -> Optional[LocalizedTemplate]:
        """Get best matching template for preferred locales"""
        # Try each preferred locale in order
        for locale_code in preferred_locales:
            template = self.get_localized_template(template_id, locale_code)
            if template:
                return template

            # Try just the language part
            if '-' in locale_code:
                language = locale_code.split('-')[0]
                for locale in self._locales.values():
                    if locale.language == language:
                        template = self.get_localized_template(template_id, locale.code)
                        if template:
                            return template

        # Fallback to default locale
        return self.get_localized_template(template_id, self._fallback_locale)

    def add_translation(
        self,
        key: str,
        locale_code: str,
        value: str
    ) -> None:
        """Add a translation"""
        if key not in self._translations:
            self._translations[key] = {}
        self._translations[key][locale_code] = value

    def add_translations_batch(
        self,
        locale_code: str,
        translations: Dict[str, str]
    ) -> None:
        """Add multiple translations for a locale"""
        for key, value in translations.items():
            self.add_translation(key, locale_code, value)

    def get_translation(
        self,
        key: str,
        locale_code: str
    ) -> Optional[str]:
        """Get translation for a key and locale"""
        locale_translations = self._translations.get(key, {})
        return locale_translations.get(locale_code)

    def translate(
        self,
        key: str,
        locale_code: str,
        default: Optional[str] = None
    ) -> str:
        """Get translation with fallback"""
        # Try exact locale
        value = self.get_translation(key, locale_code)
        if value:
            return value

        # Try just the language
        if '-' in locale_code:
            language = locale_code.split('-')[0]
            for code, trans in self._translations.get(key, {}).items():
                if code.startswith(language):
                    return trans

        # Fallback to default locale
        value = self.get_translation(key, self._fallback_locale)
        if value:
            return value

        return default or key

    def format_date(
        self,
        date_value: Any,
        locale_code: str,
        include_time: bool = False
    ) -> str:
        """Format date according to locale"""
        from datetime import datetime, date

        locale = self.get_locale(locale_code) or self._locales.get(self._fallback_locale)
        if not locale:
            return str(date_value)

        if isinstance(date_value, str):
            try:
                date_value = datetime.fromisoformat(date_value)
            except ValueError:
                return date_value

        if isinstance(date_value, datetime):
            if include_time:
                return date_value.strftime(f"{locale.date_format} {locale.time_format}")
            return date_value.strftime(locale.date_format)

        if isinstance(date_value, date):
            return date_value.strftime(locale.date_format)

        return str(date_value)

    def format_number(
        self,
        value: float,
        locale_code: str,
        decimals: int = 2
    ) -> str:
        """Format number according to locale"""
        locale = self.get_locale(locale_code) or self._locales.get(self._fallback_locale)
        if not locale:
            return str(value)

        formatted = f"{value:,.{decimals}f}"
        formatted = formatted.replace(',', 'TEMP')
        formatted = formatted.replace('.', locale.decimal_separator)
        formatted = formatted.replace('TEMP', locale.thousands_separator)

        return formatted

    def format_currency(
        self,
        value: float,
        locale_code: str,
        currency: Optional[str] = None
    ) -> str:
        """Format currency according to locale"""
        locale = self.get_locale(locale_code) or self._locales.get(self._fallback_locale)
        if not locale:
            return f"${value:.2f}"

        symbol = currency or locale.currency_symbol
        formatted = self.format_number(value, locale_code, 2)

        if locale.rtl:
            return f"{formatted} {symbol}"
        return f"{symbol}{formatted}"

    def detect_locale_from_accept_language(
        self,
        accept_language: str
    ) -> str:
        """Parse Accept-Language header and return best locale"""
        if not accept_language:
            return self._fallback_locale

        # Parse header
        languages = []
        for part in accept_language.split(','):
            part = part.strip()
            if ';' in part:
                lang, q = part.split(';')
                q = float(q.split('=')[1]) if '=' in q else 1.0
            else:
                lang = part
                q = 1.0
            languages.append((lang.strip(), q))

        # Sort by quality
        languages.sort(key=lambda x: x[1], reverse=True)

        # Find matching locale
        for lang, _ in languages:
            # Try exact match
            if lang in self._locales:
                return lang

            # Try with region
            for code in self._locales:
                if code.startswith(lang):
                    return code

        return self._fallback_locale

    def get_translations_for_locale(self, locale_code: str) -> Dict[str, str]:
        """Get all translations for a locale"""
        result = {}
        for key, translations in self._translations.items():
            if locale_code in translations:
                result[key] = translations[locale_code]
        return result

    def export_translations(self, locale_code: str) -> str:
        """Export translations as JSON"""
        translations = self.get_translations_for_locale(locale_code)
        return json.dumps(translations, indent=2, ensure_ascii=False)

    def import_translations(
        self,
        locale_code: str,
        json_content: str
    ) -> int:
        """Import translations from JSON"""
        translations = json.loads(json_content)
        count = 0
        for key, value in translations.items():
            self.add_translation(key, locale_code, value)
            count += 1
        return count
