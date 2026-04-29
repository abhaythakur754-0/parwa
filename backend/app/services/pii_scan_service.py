"""
PARWA PII Scan Service - BL07 PII Detection (Day 26)

Implements BL07: PII scanning with:
- Credit card detection
- SSN detection
- API key detection
- Password pattern detection
- Auto-redaction with reversible mapping
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy.orm import Session


class PIIScanService:
    """PII detection and redaction service."""

    # PII pattern definitions
    PATTERNS = {
        # Credit cards (various formats)
        "credit_card": [
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            # 16 digits with optional dashes/spaces
            r"\b\d{13,16}\b",  # 13-16 consecutive digits
        ],

        # Social Security Numbers (US format)
        "ssn": [
            r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",  # XXX-XX-XXXX
        ],

        # Email addresses
        "email": [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        ],

        # Phone numbers (various formats - US and International)
        "phone": [
            # US formats: 555-123-4567, (555) 123-4567, +1 555 123 4567,
            # 1-800-555-1234
            r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            # International phone with country code (no word boundary for +)
            # Matches +CC followed by groups of digits with spaces/dashes
            r"\+[\d\s-]{9,18}",
            # General international: +44 20 7946 0958, +91 98765 43210
            r"\+\d{1,3}[\s\d-]{7,15}",
            # Simple 7-digit local
            r"\b\d{3}[-.\s]?\d{4}\b",
        ],

        # API keys (common patterns)
        "api_key": [
            r"\b(?:sk|pk|api|secret|token|key)[_-]?[a-zA-Z0-9]{20,}\b",
            r"\b[a-zA-Z0-9]{32,}\b",  # Generic long alphanumeric
            r"\bghp_[a-zA-Z0-9]{36}\b",  # GitHub tokens
            r"\bsk-[a-zA-Z0-9]{20,}\b",  # OpenAI style
        ],

        # Passwords in text (common patterns)
        "password": [
            r"(?:password|passwd|pwd)[\s:=]+['\"]?\S+['\"]?",
            r"(?:secret|token|api_key)[\s:=]+['\"]?\S+['\"]?",
        ],

        # IP addresses
        "ip_address": [
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        ],

        # Bank account numbers
        "bank_account": [
            r"\b\d{8,17}\b",  # 8-17 digit account numbers
        ],

        # Dates of birth
        "dob": [
            r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b",
        ],
    }

    # Redaction patterns
    REDACTION_FORMATS = {
        "credit_card": "[REDACTED_CC]",
        "ssn": "[REDACTED_SSN]",
        "email": "[REDACTED_EMAIL]",
        "phone": "[REDACTED_PHONE]",
        "api_key": "[REDACTED_API_KEY]",
        "password": "[REDACTED_PASSWORD]",
        "ip_address": "[REDACTED_IP]",
        "bank_account": "[REDACTED_BANK]",
        "dob": "[REDACTED_DOB]",
    }

    # Redis key TTL for redaction map
    REDACTION_MAP_TTL = 86400 * 7  # 7 days

    def __init__(self, db: Session, company_id: str, redis_client=None):
        self.db = db
        self.company_id = company_id
        self.redis = redis_client

    def scan_text(
        self,
        text: str,
        scan_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Scan text for PII.

        Args:
            text: Text to scan
            scan_types: Types of PII to scan for (None = all)

        Returns:
            Dict with detected PII details
        """
        if not text:
            return {"detected": False, "findings": []}

        types_to_scan = scan_types or list(self.PATTERNS.keys())
        findings = []

        for pii_type in types_to_scan:
            if pii_type not in self.PATTERNS:
                continue

            patterns = self.PATTERNS[pii_type]
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    findings.append({
                        "type": pii_type,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                        "pattern": pattern,
                    })

        return {
            "detected": len(findings) > 0,
            "findings": findings,
            "count": len(findings),
            "types_found": list(set(f["type"] for f in findings)),
        }

    def redact_text(
        self,
        text: str,
        scan_types: Optional[List[str]] = None,
        store_map: bool = True,
    ) -> Tuple[str, Dict[str, str]]:
        """Redact PII from text.

        Args:
            text: Text to redact
            scan_types: Types of PII to redact (None = all)
            store_map: Whether to store the redaction map in Redis

        Returns:
            Tuple of (redacted_text, redaction_map)
        """
        if not text:
            return text, {}

        # Scan for PII
        scan_result = self.scan_text(text, scan_types)

        if not scan_result["detected"]:
            return text, {}

        # Deduplicate overlapping findings (keep first match for each position
        # range)
        all_findings = sorted(
            scan_result["findings"],
            key=lambda x: (x["start"], x["end"]),
        )

        deduplicated = []
        for finding in all_findings:
            # Check if this finding overlaps with any already-added finding
            overlaps = False
            for existing in deduplicated:
                # Check for overlap: [start1, end1) overlaps [start2, end2)
                if not (finding["end"] <= existing["start"]
                        or finding["start"] >= existing["end"]):
                    overlaps = True
                    break
            if not overlaps:
                deduplicated.append(finding)

        # Sort findings by position (reverse order for replacement)
        findings = sorted(
            deduplicated,
            key=lambda x: x["start"],
            reverse=True,
        )

        # Create redacted text
        redacted_text = text
        redaction_map = {}

        for finding in findings:
            pii_type = finding["type"]
            original_value = finding["value"]

            # Generate unique token for this redaction
            token_id = str(uuid.uuid4())[:8]
            redaction_token = f"[{pii_type.upper()}_{token_id}]"

            # Replace in text
            redacted_text = (
                redacted_text[:finding["start"]]
                + redaction_token
                + redacted_text[finding["end"]:]
            )

            # Store in map
            redaction_map[redaction_token] = {
                "type": pii_type,
                "original": original_value,
                "hash": hashlib.sha256(
                    original_value.encode()).hexdigest()[
                    :16],
            }

        # Store map in Redis if available
        if store_map and self.redis and redaction_map:
            map_key = f"parwa:{self.company_id}:pii_map:{uuid.uuid4()}"
            self.redis.setex(
                map_key,
                self.REDACTION_MAP_TTL,
                json.dumps(redaction_map),
            )

        return redacted_text, redaction_map

    def unredact_text(
        self,
        text: str,
        redaction_map: Dict[str, str],
    ) -> str:
        """Restore redacted text using the map.

        Args:
            text: Redacted text
            redaction_map: Redaction map from redact_text

        Returns:
            Unredacted text
        """
        if not text or not redaction_map:
            return text

        unredacted = text
        for token, info in redaction_map.items():
            unredacted = unredacted.replace(token, info["original"])

        return unredacted

    def scan_and_redact(
        self,
        text: str,
        scan_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Scan and redact PII from text.

        Args:
            text: Text to process
            scan_types: Types of PII to scan for

        Returns:
            Dict with redacted text and details
        """
        redacted_text, redaction_map = self.redact_text(text, scan_types)

        return {
            "original_text": text,
            "redacted_text": redacted_text,
            "redaction_map": redaction_map,
            "redaction_count": len(redaction_map),
            "pii_types": list(set(
                info["type"] for info in redaction_map.values()
            )),
        }

    def validate_no_pii(
        self,
        text: str,
        strict_types: Optional[List[str]] = None,
    ) -> Tuple[bool, List[Dict]]:
        """Validate that text contains no PII.

        Args:
            text: Text to validate
            strict_types: PII types that must not be present

        Returns:
            Tuple of (is_valid, violations)
        """
        # Default strict types: always block these
        default_strict = ["credit_card", "ssn", "password", "api_key"]
        types_to_check = strict_types or default_strict

        scan_result = self.scan_text(text, types_to_check)

        violations = []
        for finding in scan_result["findings"]:
            violations.append({
                "type": finding["type"],
                "position": finding["start"],
                "message": f"PII detected: {finding['type']}",
            })

        return len(violations) == 0, violations

    def mask_value(self, value: str, pii_type: str) -> str:
        """Mask a PII value for display.

        Args:
            value: Original value
            pii_type: Type of PII

        Returns:
            Masked value
        """
        if not value:
            return value

        if pii_type == "credit_card":
            # Show last 4 digits only
            return "*" * 12 + value[-4:] if len(value) >= 4 else "****"

        elif pii_type == "ssn":
            # Show last 4 digits
            return "***-**-" + value[-4:] if len(value) >= 4 else "****"

        elif pii_type == "email":
            # Show first char and domain
            parts = value.split("@")
            if len(parts) == 2:
                return parts[0][0] + "***@" + parts[1]
            return "***@***"

        elif pii_type == "phone":
            # Show last 4 digits
            return "***-***-" + value[-4:] if len(value) >= 4 else "****"

        elif pii_type == "api_key":
            # Show first 4 and last 4 chars
            if len(value) >= 12:
                return value[:4] + "..." + value[-4:]
            return "****"

        else:
            # Generic mask
            return "*" * min(len(value), 8)

    def get_pii_stats(self, text: str) -> Dict[str, int]:
        """Get statistics about PII in text.

        Args:
            text: Text to analyze

        Returns:
            Dict with count per PII type
        """
        scan_result = self.scan_text(text)

        stats = {}
        for finding in scan_result["findings"]:
            pii_type = finding["type"]
            stats[pii_type] = stats.get(pii_type, 0) + 1

        return stats
