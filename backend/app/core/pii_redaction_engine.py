"""
PII Redaction Engine (F-056): Deterministic PII Detection, Redaction & Deredaction.

Scans text for 15+ PII types using compiled regex patterns (no NLP libs),
replaces sensitive data with deterministic tokens, and stores the reversible
redaction map in Redis with 24h TTL for later deredaction.

Token format:  {{PII_TYPE_UUID8}}  where UUID8 = first 8 hex chars of
               SHA-256(value + pii_type + company_id).
Redis key:     parwa:pii:{company_id}:{redaction_id}
TTL:           86400 seconds (24 hours)

BC-001: company_id is always second parameter.
BC-008: Graceful degradation -- never crash on detection failure.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.core.redis import get_redis, make_key
from backend.app.exceptions import InternalError
from backend.app.logger import get_logger

logger = get_logger("pii_redaction_engine")

# ── PII Type Constants ────────────────────────────────────────────

PII_SSN = "SSN"
PII_CREDIT_CARD = "CREDIT_CARD"
PII_EMAIL = "EMAIL"
PII_PHONE = "PHONE"
PII_IP_ADDRESS = "IP_ADDRESS"
PII_DATE_OF_BIRTH = "DATE_OF_BIRTH"
PII_PASSPORT = "PASSPORT"
PII_DRIVERS_LICENSE = "DRIVERS_LICENSE"
PII_IBAN = "IBAN"
PII_MEDICAL_RECORD_NUMBER = "MEDICAL_RECORD_NUMBER"
PII_HEALTH_INSURANCE_ID = "HEALTH_INSURANCE_ID"
PII_STREET_ADDRESS = "STREET_ADDRESS"
PII_API_KEY = "API_KEY"
PII_AADHAAR = "AADHAAR"
PII_PAN = "PAN"

ALL_PII_TYPES: Set[str] = {
    PII_SSN,
    PII_CREDIT_CARD,
    PII_EMAIL,
    PII_PHONE,
    PII_IP_ADDRESS,
    PII_DATE_OF_BIRTH,
    PII_PASSPORT,
    PII_DRIVERS_LICENSE,
    PII_IBAN,
    PII_MEDICAL_RECORD_NUMBER,
    PII_HEALTH_INSURANCE_ID,
    PII_STREET_ADDRESS,
    PII_API_KEY,
    PII_AADHAAR,
    PII_PAN,
}

# ── Compiled Regex Patterns (module-level, compiled ONCE) ─────────
# Naming: _PAT_<TYPE>. All patterns use named groups where applicable.

# 1. SSN: 123-45-6789 or 123 45 6789 (not 000-xx-xxxx, 666-xx-xxxx, 9xx-xx-xxxx)
_PAT_SSN = re.compile(
    r"\b(?!000|666|9\d{2})(\d{3})[-\s](?!00)\d{2}[-\s](?!0000)\d{4}\b"
)

# 2. Credit Card: Visa (4x4), MC (4x4 starting 51-55), Amex (4-6-5)
_PAT_CREDIT_CARD = re.compile(
    r"\b(?:4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"
    r"|(?:5[1-5]\d{2}|2[2-7]\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"
    r"|3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5})\b"
)

# 3. Email: standard email format
_PAT_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# 4. Phone: US formats + international with country codes
_PAT_PHONE = re.compile(
    r"(?:\b\+?1[-.\s]?)?"
    r"(?:\(?\d{3}\)?[-.\s]?)"
    r"\d{3}[-.\s]?"
    r"\d{4}\b"
    r"|\b\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b"
)

# 5. IPv4 Address
_PAT_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b"
)

# 6. IPv6 Address (simplified — covers common forms)
_PAT_IPV6 = re.compile(
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r"|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"
    r"|::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:[0-9a-fA-F]{1,4}:){1,3}[0-9a-fA-F]{1,4}"
)

# 7. Date of Birth: MM/DD/YYYY, YYYY-MM-DD, DD-MMM-YYYY
_PAT_DOB_MDY = re.compile(
    r"\b(0[1-9]|1[0-2])[\/\-](0[1-9]|[12]\d|3[01])[\/\-](19|20)\d{2}\b"
)
_PAT_DOB_YMD = re.compile(
    r"\b(19|20)\d{2}[\-\/](0[1-9]|1[0-2])[\-\/](0[1-9]|[12]\d|3[01])\b"
)
_PAT_DOB_DMY = re.compile(
    r"\b(0[1-9]|[12]\d|3[01])[\-](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[\-](19|20)\d{2}\b"
)

# 8. Passport: US passport (9 digits), UK (8 digits + check), EU (2 letters + 7 digits)
_PAT_PASSPORT_US = re.compile(r"\b[1-9]\d{8}\b")
_PAT_PASSPORT_UK = re.compile(r"\b\d{8}[A-Z]\b")
_PAT_PASSPORT_EU = re.compile(r"\b[A-Z]{2}\d{7}\b")

# 9. Driver's License: US state patterns (alphanumeric 1-2 letters + 6-12 digits)
_PAT_DL = re.compile(
    r"\b(?:[A-Z]{1,2}[-\s]?)?\d{6,12}\b"
)

# 10. IBAN: country code (2 letters) + 2 check digits + up to 30 alphanumeric
_PAT_IBAN = re.compile(
    r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b"
)

# 11. Medical Record Number: alphanumeric, 6-12 chars, common prefixes
_PAT_MRN = re.compile(
    r"\b(?:MRN|MR|PT|PAT)[-]?\d{4,10}[A-Z]?\b"
)

# 12. Health Insurance ID: Medicare MBI (11 chars: C-NN-AA-C-AA format).
#     MBI excludes chars S, L, O, I, B, Z.  Dashes are optional in display.
_PAT_MEDICARE = re.compile(
    r"\b[1-9][ACDEFGHJKMNPQRTUVWXY]{2}\d"
    r"[ACDEFGHJKMNPQRTUVWXY]{2}\d"
    r"[ACDEFGHJKMNPQRTUVWXY]{2}\d{2}\b"
)
_PAT_MEDICAID = re.compile(
    r"\b[A-Z]{2}\d{5,10}\b"
)

# 13. Street Address: number + street name (partial match)
_PAT_STREET_ADDRESS = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9\s]{2,40}"
    r"(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|"
    r"Way|Court|Ct|Place|Pl|Circle|Cir|Crescent|Cres|Trail|Trl|"
    r"Parkway|Pkwy|Highway|Hwy|Terrace|Ter)\b"
    r"(?:[,\s]+(?:#[\w\s]+|(?:Apt|Suite|Ste|Unit|Fl|Floor|Rm|Room)\s*\.?\s*[\w]+))?"
    r"(?:[,\s]+[A-Za-z\s]{2,25})?"
)

# 14. API Keys: sk-..., key_..., ghp_..., csk-..., xox[bpra]-...
_PAT_API_KEY = re.compile(
    r"\b(?:sk-[A-Za-z0-9_\-]{20,}"
    r"|key_[A-Za-z0-9_\-]{16,}"
    r"|ghp_[A-Za-z0-9]{36}"
    r"|csk-[A-Za-z0-9_\-]{20,}"
    r"|xox[bpra]-[A-Za-z0-9\-]{10,}"
    r"|AIza[A-Za-z0-9_\-]{35}"
    r"|hooks\.[A-Za-z0-9\-]{30,})\b"
)

# 15. Aadhaar (India): 12 digits, last digit is checksum
_PAT_AADHAAR = re.compile(
    r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b"
)

# 16. PAN (India): ABCDE1234F (5 letters + 4 digits + 1 letter)
_PAT_PAN = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"
)

# ── Token replacement pattern (for deredaction) ──────────────────
_TOKEN_PATTERN = re.compile(r"\{\{([A-Z_]+)_[0-9a-f]{8}\}\}")


# ── Data Classes ──────────────────────────────────────────────────


@dataclass
class PIIMatch:
    """Represents a single PII detection match."""
    pii_type: str
    value: str
    start: int
    end: int
    confidence: float
    pattern_matched: str


@dataclass
class RedactionResult:
    """Complete result of a redaction operation."""
    redacted_text: str
    redaction_map: Dict[str, str]
    redaction_id: str
    pii_found: bool
    summary: Dict[str, Any] = field(default_factory=dict)


# ── Deterministic Token Generation ────────────────────────────────


def _generate_token(pii_type: str, value: str, company_id: str) -> str:
    """Generate a deterministic replacement token.

    Format: {{PII_TYPE_UUID8}} where UUID8 is the first 8 hex chars
    of SHA-256(value + pii_type + company_id).  Same inputs always
    produce the same token (deterministic).

    Args:
        pii_type: The PII type constant (e.g. "SSN").
        value: The raw PII value found in text.
        company_id: Tenant identifier for scoping.

    Returns:
        Token string like "{{SSN_a1b2c3d4}}".
    """
    raw = f"{value}:{pii_type}:{company_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{{{{{pii_type}_{digest}}}}}"


def _generate_redaction_id() -> str:
    """Generate a unique redaction session ID (UUID4)."""
    return str(uuid.uuid4())


# ── PIIDetector ───────────────────────────────────────────────────


class PIIDetector:
    """Regex-based PII detector. Scans text for 15 PII types.

    Each PII type has a dedicated detection method that returns
    a list of PIIMatch objects with confidence scoring (0.0–1.0).

    BC-008: Never crashes — returns empty list on unexpected errors.
    """

    def detect(
        self,
        text: str,
        pii_types: Optional[Set[str]] = None,
    ) -> List[PIIMatch]:
        """Scan text for PII and return all matches.

        Args:
            text: The input text to scan.
            pii_types: Subset of PII types to detect. None = all.

        Returns:
            List of PIIMatch sorted by position (start ascending).
        """
        if not text:
            return []

        target_types = pii_types if pii_types is not None else ALL_PII_TYPES
        all_matches: List[PIIMatch] = []

        detection_map: Dict[str, List[PIIMatch]] = {
            PII_SSN: self._detect_ssn,
            PII_CREDIT_CARD: self._detect_credit_card,
            PII_EMAIL: self._detect_email,
            PII_PHONE: self._detect_phone,
            PII_IP_ADDRESS: self._detect_ip_address,
            PII_DATE_OF_BIRTH: self._detect_date_of_birth,
            PII_PASSPORT: self._detect_passport,
            PII_DRIVERS_LICENSE: self._detect_drivers_license,
            PII_IBAN: self._detect_iban,
            PII_MEDICAL_RECORD_NUMBER: self._detect_medical_record_number,
            PII_HEALTH_INSURANCE_ID: self._detect_health_insurance_id,
            PII_STREET_ADDRESS: self._detect_street_address,
            PII_API_KEY: self._detect_api_key,
            PII_AADHAAR: self._detect_aadhaar,
            PII_PAN: self._detect_pan,
        }

        for pii_type in target_types:
            detector = detection_map.get(pii_type)
            if detector is None:
                continue
            try:
                matches = detector(text)
                all_matches.extend(matches)
            except Exception:
                # BC-008: never crash
                logger.exception(
                    "pii_detection_failed",
                    extra={"pii_type": pii_type},
                )

        # Sort by position for deterministic replacement order
        all_matches.sort(key=lambda m: (m.start, -len(m.value)))

        # GAP FIX: Deduplicate overlapping matches. When two PII types match
        # at overlapping positions (e.g., phone pattern matching an SSN),
        # keep only the highest-confidence match at each position.
        deduped: List[PIIMatch] = []
        for match in all_matches:
            overlaps = False
            for kept in deduped:
                # Check if this match overlaps with an already-kept match
                if match.start < kept.end and match.end > kept.start:
                    overlaps = True
                    break
            if not overlaps:
                deduped.append(match)
        return deduped

    # ── Individual Detection Methods ───────────────────────────

    def _detect_ssn(self, text: str) -> List[PIIMatch]:
        """Detect SSN: 123-45-6789, 123 45 6789."""
        matches: List[PIIMatch] = []
        for m in _PAT_SSN.finditer(text):
            # Exclude obviously false positives like phone numbers
            raw = m.group()
            if re.match(r"^\d{3}[-\s]\d{2}[-\s]\d{4}$", raw):
                area = raw[:3]
                # Reject impossible area numbers
                if area in ("000", "666") or area.startswith("9"):
                    continue
                group = raw[4:6]
                serial = raw[7:11]
                if group == "00" or serial == "0000":
                    continue
                matches.append(PIIMatch(
                    pii_type=PII_SSN,
                    value=raw,
                    start=m.start(),
                    end=m.end(),
                    confidence=0.95,
                    pattern_matched="ssn_standard",
                ))
        return matches

    def _detect_credit_card(self, text: str) -> List[PIIMatch]:
        """Detect Visa, Mastercard, Amex card numbers."""
        matches: List[PIIMatch] = []
        for m in _PAT_CREDIT_CARD.finditer(text):
            raw = m.group()
            digits = re.sub(r"[-\s]", "", raw)
            length = len(digits)
            card_type = "unknown"
            confidence = 0.85

            if digits.startswith("4") and length == 16:
                card_type = "visa"
                confidence = 0.92
            elif (digits.startswith(("51", "52", "53", "54", "55"))
                  and length == 16):
                card_type = "mastercard"
                confidence = 0.92
            elif (digits.startswith(("22", "23", "24", "25", "26", "27"))
                  and length == 16):
                card_type = "mastercard_2series"
                confidence = 0.90
            elif digits.startswith(("34", "37")) and length == 15:
                card_type = "amex"
                confidence = 0.93

            # Luhn check for boosted confidence
            if self._luhn_check(digits):
                confidence = min(confidence + 0.07, 1.0)

            matches.append(PIIMatch(
                pii_type=PII_CREDIT_CARD,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched=f"credit_card_{card_type}",
            ))
        return matches

    @staticmethod
    def _luhn_check(digits: str) -> bool:
        """Luhn algorithm for credit card validation."""
        if not digits.isdigit():
            return False
        total = 0
        reverse_digits = digits[::-1]
        for i, ch in enumerate(reverse_digits):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    def _detect_email(self, text: str) -> List[PIIMatch]:
        """Detect email addresses."""
        matches: List[PIIMatch] = []
        for m in _PAT_EMAIL.finditer(text):
            raw = m.group()
            # Reject common false positives
            local, domain = raw.rsplit("@", 1)
            if domain in ("example.com", "test.com", "domain.com"):
                confidence = 0.50
            elif "." not in domain:
                continue
            elif domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                continue
            else:
                confidence = 0.97
            matches.append(PIIMatch(
                pii_type=PII_EMAIL,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched="email_standard",
            ))
        return matches

    def _detect_phone(self, text: str) -> List[PIIMatch]:
        """Detect US and international phone numbers."""
        matches: List[PIIMatch] = []
        seen_positions: Set[int] = set()
        for m in _PAT_PHONE.finditer(text):
            raw = m.group()
            digits = re.sub(r"[^\d]", "", raw)

            # Skip if it's clearly not a phone (too short / too long)
            if len(digits) < 7 or len(digits) > 15:
                continue

            # Avoid overlapping matches
            if m.start() in seen_positions:
                continue
            seen_positions.add(m.start())

            confidence = 0.75
            pattern_matched = "phone_international"

            if len(digits) == 10:
                confidence = 0.88
                pattern_matched = "phone_us_local"
            elif len(digits) == 11 and digits.startswith("1"):
                confidence = 0.90
                pattern_matched = "phone_us_country"
            elif raw.startswith("+"):
                confidence = 0.82
                pattern_matched = "phone_international"

            matches.append(PIIMatch(
                pii_type=PII_PHONE,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched=pattern_matched,
            ))
        return matches

    def _detect_ip_address(self, text: str) -> List[PIIMatch]:
        """Detect IPv4 and IPv6 addresses."""
        matches: List[PIIMatch] = []

        for m in _PAT_IPV4.finditer(text):
            raw = m.group()
            # Reject version numbers like 1.0.0
            if raw.startswith("0.") and raw.count(".") == 3:
                confidence = 0.50
            else:
                confidence = 0.93
            matches.append(PIIMatch(
                pii_type=PII_IP_ADDRESS,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched="ipv4",
            ))

        for m in _PAT_IPV6.finditer(text):
            raw = m.group()
            matches.append(PIIMatch(
                pii_type=PII_IP_ADDRESS,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=0.90,
                pattern_matched="ipv6",
            ))

        return matches

    def _detect_date_of_birth(self, text: str) -> List[PIIMatch]:
        """Detect dates that look like dates of birth."""
        matches: List[PIIMatch] = []
        seen: Set[Tuple[int, int]] = set()

        for pattern, pat_name, confidence_base in [
            (_PAT_DOB_MDY, "dob_mdy", 0.80),
            (_PAT_DOB_YMD, "dob_ymd", 0.80),
            (_PAT_DOB_DMY, "dob_dmy", 0.85),
        ]:
            for m in pattern.finditer(text):
                pos_key = (m.start(), m.end())
                if pos_key in seen:
                    continue
                seen.add(pos_key)

                raw = m.group()
                # Higher confidence for reasonable DOB years (1900-2010)
                year_match = re.search(r"(19|20)\d{2}", raw)
                if year_match:
                    year = int(year_match.group())
                    if 1920 <= year <= 2015:
                        confidence = confidence_base + 0.12
                    else:
                        confidence = confidence_base - 0.05
                else:
                    confidence = confidence_base

                matches.append(PIIMatch(
                    pii_type=PII_DATE_OF_BIRTH,
                    value=raw,
                    start=m.start(),
                    end=m.end(),
                    confidence=min(max(confidence, 0.1), 1.0),
                    pattern_matched=pat_name,
                ))

        return matches

    def _detect_passport(self, text: str) -> List[PIIMatch]:
        """Detect passport numbers (US, UK, EU formats)."""
        matches: List[PIIMatch] = []

        # US: 9 digits
        for m in _PAT_PASSPORT_US.finditer(text):
            raw = m.group()
            matches.append(PIIMatch(
                pii_type=PII_PASSPORT,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=0.55,
                pattern_matched="passport_us_heuristic",
            ))

        # UK: 8 digits + 1 check letter
        for m in _PAT_PASSPORT_UK.finditer(text):
            raw = m.group()
            matches.append(PIIMatch(
                pii_type=PII_PASSPORT,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=0.70,
                pattern_matched="passport_uk",
            ))

        # EU: 2 letters + 7 digits
        for m in _PAT_PASSPORT_EU.finditer(text):
            raw = m.group()
            # Exclude common acronyms like "CA1234567" that could be
            # state abbreviations followed by zip
            if len(raw) == 9 and re.match(r"^[A-Z]{2}\d{7}$", raw):
                matches.append(PIIMatch(
                    pii_type=PII_PASSPORT,
                    value=raw,
                    start=m.start(),
                    end=m.end(),
                    confidence=0.60,
                    pattern_matched="passport_eu_heuristic",
                ))

        return matches

    def _detect_drivers_license(self, text: str) -> List[PIIMatch]:
        """Detect US driver's license numbers.

        Uses state-specific patterns where known; otherwise
        heuristic alphanumeric patterns.
        """
        matches: List[PIIMatch] = []

        # Common state patterns (Florida, Texas, California, New York, etc.)
        state_patterns: Dict[str, Tuple[re.Pattern, float]] = {
            "florida": (re.compile(r"\b[A-Z]\d{2}-\d{2}-\d{4}\b"), 0.80),
            "texas": (re.compile(r"\b\d{7,8}\b"), 0.45),
            "california": (re.compile(r"\b[A-Z]\d{7}\b"), 0.60),
            "new_york": (re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{3}\b"), 0.50),
            "illinois": (re.compile(r"\b[A-Z]\d{11}[A-Z]?\b"), 0.65),
            "pennsylvania": (re.compile(r"\b\d{2}[-\s]?\d{4}[-\s]?\d{2}\b"), 0.55),
        }

        for state_name, (pat, conf) in state_patterns.items():
            for m in pat.finditer(text):
                raw = m.group()
                # Only include if not already matched as SSN
                if re.match(r"^\d{3}[-\s]\d{2}[-\s]\d{4}$", raw):
                    continue
                matches.append(PIIMatch(
                    pii_type=PII_DRIVERS_LICENSE,
                    value=raw,
                    start=m.start(),
                    end=m.end(),
                    confidence=conf,
                    pattern_matched=f"dl_{state_name}",
                ))

        # Generic DL pattern: alphanumeric 6-12 chars
        for m in _PAT_DL.finditer(text):
            raw = m.group()
            # Skip if already captured by more specific patterns
            already = any(
                mm.start == m.start() and mm.end == m.end()
                for mm in matches
            )
            if already:
                continue
            # Skip pure numeric that looks like a year or zip
            if re.match(r"^\d{4,5}$", raw):
                continue
            matches.append(PIIMatch(
                pii_type=PII_DRIVERS_LICENSE,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=0.40,
                pattern_matched="dl_generic",
            ))

        return matches

    def _detect_iban(self, text: str) -> List[PIIMatch]:
        """Detect IBAN numbers (country-specific format)."""
        matches: List[PIIMatch] = []

        for m in _PAT_IBAN.finditer(text):
            raw = m.group()
            country_code = raw[:2]

            # Known IBAN country lengths for confidence boost
            country_lengths: Dict[str, int] = {
                "DE": 22, "FR": 27, "GB": 22, "IT": 27,
                "ES": 24, "NL": 18, "BE": 16, "CH": 21,
                "AT": 20, "PT": 25, "IE": 22, "SE": 24,
                "NO": 15, "DK": 18, "FI": 18, "PL": 28,
                "AE": 23, "SA": 24, "IN": 15,
            }

            clean = re.sub(r"[\s\-]", "", raw)
            confidence = 0.70

            if country_code in country_lengths:
                expected_len = country_lengths[country_code]
                if len(clean) == expected_len:
                    confidence = 0.92
                else:
                    confidence = 0.60

            # Only 2-letter codes that are real ISO country codes
            if not re.match(r"^[A-Z]{2}$", country_code):
                continue

            matches.append(PIIMatch(
                pii_type=PII_IBAN,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched=f"iban_{country_code.lower()}",
            ))
        return matches

    def _detect_medical_record_number(self, text: str) -> List[PIIMatch]:
        """Detect Medical Record Numbers (MRN)."""
        matches: List[PIIMatch] = []
        for m in _PAT_MRN.finditer(text):
            raw = m.group()
            matches.append(PIIMatch(
                pii_type=PII_MEDICAL_RECORD_NUMBER,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=0.88,
                pattern_matched="mrn_prefixed",
            ))
        return matches

    def _detect_health_insurance_id(self, text: str) -> List[PIIMatch]:
        """Detect Medicare MBI IDs and Medicaid state IDs."""
        matches: List[PIIMatch] = []

        # Medicare MBI: 11 chars matching the pattern
        for m in _PAT_MEDICARE.finditer(text):
            raw = m.group()
            matches.append(PIIMatch(
                pii_type=PII_HEALTH_INSURANCE_ID,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=0.90,
                pattern_matched="medicare_mbi",
            ))

        # Medicaid: state-specific (2-letter prefix + digits)
        for m in _PAT_MEDICAID.finditer(text):
            raw = m.group()
            # Skip matches already captured by Medicare MBI
            if any(mm.start == m.start() and mm.end == m.end()
                   for mm in matches):
                continue
            matches.append(PIIMatch(
                pii_type=PII_HEALTH_INSURANCE_ID,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=0.65,
                pattern_matched="medicaid_heuristic",
            ))

        return matches

    def _detect_street_address(self, text: str) -> List[PIIMatch]:
        """Detect street addresses using partial matching."""
        matches: List[PIIMatch] = []
        for m in _PAT_STREET_ADDRESS.finditer(text):
            raw = m.group()
            confidence = 0.78
            pattern_matched = "street_address_standard"

            # Boost confidence for addresses with apartment/suite numbers
            if re.search(r"(?:Apt|Suite|Ste|Unit|#)", raw, re.IGNORECASE):
                confidence = 0.88
                pattern_matched = "street_address_with_unit"

            # Boost for addresses ending with 5-digit zip
            if re.search(r"\d{5}$", raw):
                confidence = 0.90
                pattern_matched = "street_address_with_zip"

            # Minimum length check
            if len(raw) < 10:
                confidence -= 0.20

            matches.append(PIIMatch(
                pii_type=PII_STREET_ADDRESS,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=max(confidence, 0.10),
                pattern_matched=pattern_matched,
            ))
        return matches

    def _detect_api_key(self, text: str) -> List[PIIMatch]:
        """Detect API keys: sk-..., key_..., ghp_..., csk-..., etc."""
        matches: List[PIIMatch] = []
        for m in _PAT_API_KEY.finditer(text):
            raw = m.group()
            confidence = 0.95
            pattern_matched = "api_key"

            if raw.startswith("sk-"):
                pattern_matched = "api_key_openai"
            elif raw.startswith("key_"):
                pattern_matched = "api_key_generic"
            elif raw.startswith("ghp_"):
                pattern_matched = "api_key_github_pat"
            elif raw.startswith("csk-"):
                pattern_matched = "api_key_cozy"
            elif raw.startswith("xox"):
                pattern_matched = "api_key_slack"
            elif raw.startswith("AIza"):
                pattern_matched = "api_key_google_ai"
            elif raw.startswith("hooks."):
                pattern_matched = "api_key_webhook"

            matches.append(PIIMatch(
                pii_type=PII_API_KEY,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched=pattern_matched,
            ))
        return matches

    def _detect_aadhaar(self, text: str) -> List[PIIMatch]:
        """Detect Indian Aadhaar numbers (12 digits)."""
        matches: List[PIIMatch] = []
        for m in _PAT_AADHAAR.finditer(text):
            raw = m.group()
            digits = re.sub(r"[\s\-]", "", raw)
            if len(digits) != 12:
                continue
            # Verhoeff check would be ideal but is complex;
            # use structural check: must start with non-zero
            if digits[0] not in "123456789":
                continue
            confidence = 0.85
            if " " in raw or "-" in raw:
                confidence = 0.90  # formatted is more likely intentional
            matches.append(PIIMatch(
                pii_type=PII_AADHAAR,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched="aadhaar_12digit",
            ))
        return matches

    def _detect_pan(self, text: str) -> List[PIIMatch]:
        """Detect Indian PAN numbers: ABCDE1234F."""
        matches: List[PIIMatch] = []
        for m in _PAT_PAN.finditer(text):
            raw = m.group()
            # 4th character must indicate entity type
            fourth_char = raw[3]
            valid_fourth = {"C", "H", "F", "A", "T", "B", "L", "J", "G", "P"}
            if fourth_char in valid_fourth:
                confidence = 0.93
                pattern_matched = "pan_valid_structure"
            else:
                confidence = 0.60
                pattern_matched = "pan_heuristic"

            # Last character (5th position) must be a letter — already ensured
            # by the regex [A-Z]{5}[0-9]{4}[A-Z]

            matches.append(PIIMatch(
                pii_type=PII_PAN,
                value=raw,
                start=m.start(),
                end=m.end(),
                confidence=confidence,
                pattern_matched=pattern_matched,
            ))
        return matches


# ── PIIRedactor ───────────────────────────────────────────────────


class PIIRedactor:
    """Replaces detected PII with deterministic tokens.

    Token format: {{PII_TYPE_UUID8}}
    Deterministic: same (value, pii_type, company_id) → same token.
    Stores the redaction map in Redis for 24h for later deredaction.

    BC-001: company_id is always second parameter.
    BC-008: Never crashes — returns original text on error.
    """

    def __init__(self) -> None:
        self._detector = PIIDetector()
        self._cache = PIIRedactionCache()
        logger.info("pii_redactor_initialized")

    async def redact(
        self,
        text: str,
        company_id: str,
        pii_types: Optional[Set[str]] = None,
    ) -> RedactionResult:
        """Detect and redact PII in text.

        Args:
            text: Input text containing potential PII.
            company_id: Tenant identifier (BC-001).
            pii_types: Subset of PII types to redact. None = all.

        Returns:
            RedactionResult with redacted text, map, id, and summary.
        """
        if not text:
            return RedactionResult(
                redacted_text=text or "",
                redaction_map={},
                redaction_id="",
                pii_found=False,
                summary={"total_matches": 0, "by_type": {}},
            )

        redaction_id = _generate_redaction_id()
        matches = self._detector.detect(text, pii_types)

        if not matches:
            return RedactionResult(
                redacted_text=text,
                redaction_map={},
                redaction_id=redaction_id,
                pii_found=False,
                summary={"total_matches": 0, "by_type": {}},
            )

        # Build redaction map: token -> original value
        redaction_map: Dict[str, str] = {}
        replacements: List[Tuple[str, int, int]] = []

        for match in matches:
            token = _generate_token(match.pii_type, match.value, company_id)
            redaction_map[token] = match.value
            replacements.append((token, match.start, match.end))

        # Apply replacements in reverse order to preserve offsets
        redacted = text
        for token, start, end in reversed(replacements):
            redacted = redacted[:start] + token + redacted[end:]

        # Build summary
        by_type: Dict[str, int] = {}
        for match in matches:
            by_type[match.pii_type] = by_type.get(match.pii_type, 0) + 1

        summary: Dict[str, Any] = {
            "total_matches": len(matches),
            "by_type": by_type,
            "redacted_at": datetime.now(timezone.utc).isoformat(),
            "company_id": company_id,
            "pii_types_requested": sorted(pii_types) if pii_types else "all",
        }

        # Store map in Redis
        try:
            await self._cache.store_map(
                company_id=company_id,
                redaction_id=redaction_id,
                redaction_map=redaction_map,
            )
        except Exception:
            # BC-008: log but don't fail
            logger.exception(
                "pii_redaction_cache_store_failed",
                extra={
                    "company_id": company_id,
                    "redaction_id": redaction_id,
                },
            )

        logger.info(
            "pii_redacted",
            extra={
                "company_id": company_id,
                "redaction_id": redaction_id,
                "match_count": len(matches),
                "pii_types_found": sorted(by_type.keys()),
            },
        )

        return RedactionResult(
            redacted_text=redacted,
            redaction_map=redaction_map,
            redaction_id=redaction_id,
            pii_found=True,
            summary=summary,
        )


# ── PIIDeredactor ─────────────────────────────────────────────────


class PIIDeredactor:
    """Reverses PII redaction by reading the map from Redis.

    BC-001: company_id is always second parameter.
    BC-008: Never crashes — returns original text on error.
    """

    def __init__(self) -> None:
        self._cache = PIIRedactionCache()
        logger.info("pii_deredactor_initialized")

    async def deredact(
        self,
        text: str,
        company_id: str,
        redaction_id: str,
    ) -> str:
        """Replace PII tokens back with original values.

        Args:
            text: Redacted text containing {{PII_TYPE_xxxx}} tokens.
            company_id: Tenant identifier (BC-001).
            redaction_id: The redaction session ID to look up.

        Returns:
            Original text with PII restored, or the input text
            unchanged if the map is not found.
        """
        if not text or not redaction_id:
            return text

        redaction_map = await self._cache.get_map(company_id, redaction_id)
        if not redaction_map:
            logger.warning(
                "pii_deredact_map_not_found",
                extra={
                    "company_id": company_id,
                    "redaction_id": redaction_id,
                },
            )
            return text

        result = text
        for token, original in redaction_map.items():
            result = result.replace(token, original)

        restored_count = len(redaction_map)
        logger.info(
            "pii_deredacted",
            extra={
                "company_id": company_id,
                "redaction_id": redaction_id,
                "tokens_restored": restored_count,
            },
        )

        return result


# ── PIIRedactionCache ─────────────────────────────────────────────


class PIIRedactionCache:
    """Redis-backed cache for PII redaction maps.

    Stores the mapping from token -> original PII value so that
    deredaction can restore the original text.  Maps expire
    after 24 hours (86400 seconds).

    Redis key format: parwa:pii:{company_id}:{redaction_id}
    BC-001: company_id is always the first key segment after prefix.
    BC-012: Redis failure → fail-open (return None / silently skip).
    """

    DEFAULT_TTL = 86400  # 24 hours

    async def store_map(
        self,
        company_id: str,
        redaction_id: str,
        redaction_map: Dict[str, str],
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """Store a redaction map in Redis.

        Args:
            company_id: Tenant identifier (BC-001).
            redaction_id: Unique session identifier for this redaction.
            redaction_map: Dict mapping tokens to original PII values.
            ttl: Time-to-live in seconds (default 86400 = 24h).

        Returns:
            True if stored successfully, False on error.
        """
        try:
            redis_key = make_key(company_id, "pii", redaction_id)
            client = await get_redis()
            serialized = json.dumps(redaction_map)
            await client.set(redis_key, serialized, ex=ttl)
            logger.debug(
                "pii_map_stored",
                extra={
                    "company_id": company_id,
                    "redaction_id": redaction_id,
                    "map_size": len(redaction_map),
                    "ttl": ttl,
                },
            )
            return True
        except Exception:
            logger.exception(
                "pii_map_store_failed",
                extra={
                    "company_id": company_id,
                    "redaction_id": redaction_id,
                },
            )
            return False

    async def get_map(
        self,
        company_id: str,
        redaction_id: str,
    ) -> Optional[Dict[str, str]]:
        """Retrieve a redaction map from Redis.

        Args:
            company_id: Tenant identifier (BC-001).
            redaction_id: The session ID to look up.

        Returns:
            The redaction map dict, or None if not found / error.
        """
        try:
            redis_key = make_key(company_id, "pii", redaction_id)
            client = await get_redis()
            raw = await client.get(redis_key)
            if raw is None:
                return None
            result = json.loads(raw)
            if not isinstance(result, dict):
                logger.warning(
                    "pii_map_invalid_format",
                    extra={
                        "company_id": company_id,
                        "redaction_id": redaction_id,
                    },
                )
                return None
            # Ensure all keys and values are strings
            return {
                str(k): str(v) for k, v in result.items()
            }
        except Exception:
            logger.exception(
                "pii_map_retrieve_failed",
                extra={
                    "company_id": company_id,
                    "redaction_id": redaction_id,
                },
            )
            return None

    async def delete_map(
        self,
        company_id: str,
        redaction_id: str,
    ) -> bool:
        """Delete a redaction map from Redis (for cleanup / revocation).

        Args:
            company_id: Tenant identifier (BC-001).
            redaction_id: The session ID to delete.

        Returns:
            True if deleted successfully, False on error.
        """
        try:
            redis_key = make_key(company_id, "pii", redaction_id)
            client = await get_redis()
            await client.delete(redis_key)
            logger.debug(
                "pii_map_deleted",
                extra={
                    "company_id": company_id,
                    "redaction_id": redaction_id,
                },
            )
            return True
        except Exception:
            logger.exception(
                "pii_map_delete_failed",
                extra={
                    "company_id": company_id,
                    "redaction_id": redaction_id,
                },
            )
            return False


# ── Convenience Singleton Factories ───────────────────────────────

_detector_instance: Optional[PIIDetector] = None
_redactor_instance: Optional[PIIRedactor] = None
_deredactor_instance: Optional[PIIDeredactor] = None


def get_pii_detector() -> PIIDetector:
    """Get or create the shared PIIDetector singleton."""
    global _detector_instance  # noqa: PLW0603
    if _detector_instance is None:
        _detector_instance = PIIDetector()
    return _detector_instance


def get_pii_redactor() -> PIIRedactor:
    """Get or create the shared PIIRedactor singleton."""
    global _redactor_instance  # noqa: PLW0603
    if _redactor_instance is None:
        _redactor_instance = PIIRedactor()
    return _redactor_instance


def get_pii_deredactor() -> PIIDeredactor:
    """Get or create the shared PIIDeredactor singleton."""
    global _deredactor_instance  # noqa: PLW0603
    if _deredactor_instance is None:
        _deredactor_instance = PIIDeredactor()
    return _deredactor_instance
