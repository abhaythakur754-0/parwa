"""
PARWA Jurisdiction-Based Compliance Rules.

Provides jurisdiction-specific compliance rules for customer communications,
including TCPA (US), GDPR (EU), DPDPA (India), and other regional regulations.

Key Features:
- Jurisdiction detection from country/region codes
- Compliance rules per jurisdiction
- Communication time windows
- Consent requirements
- Opt-out handling
"""
from typing import Optional, Dict, Any, List
from datetime import time, datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class JurisdictionCode(str, Enum):
    """Supported jurisdiction codes."""
    US = "US"  # United States - TCPA
    EU = "EU"  # European Union - GDPR
    UK = "UK"  # United Kingdom - UK GDPR
    IN = "IN"  # India - DPDPA
    CA = "CA"  # Canada - CASL
    AU = "AU"  # Australia - Spam Act
    SG = "SG"  # Singapore - PDPA
    JP = "JP"  # Japan - APPI
    BR = "BR"  # Brazil - LGPD
    OTHER = "OTHER"


class ConsentType(str, Enum):
    """Types of consent required."""
    EXPRESS_WRITTEN = "express_written"
    EXPRESS_ORAL = "express_oral"
    IMPLIED = "implied"
    OPT_OUT = "opt_out"
    NONE_REQUIRED = "none_required"


class CommunicationType(str, Enum):
    """Types of communication channels."""
    VOICE = "voice"
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class TimeWindow(BaseModel):
    """Allowed communication time window."""
    start_hour: int = Field(ge=0, le=23)
    start_minute: int = Field(ge=0, le=59, default=0)
    end_hour: int = Field(ge=0, le=23)
    end_minute: int = Field(ge=0, le=59, default=0)

    model_config = ConfigDict()

    def is_within_window(self, check_time: Optional[time] = None) -> bool:
        """
        Check if given time is within the allowed window.

        Args:
            check_time: Time to check. Defaults to current time.

        Returns:
            True if within allowed window
        """
        if check_time is None:
            check_time = datetime.now().time()

        start = time(self.start_hour, self.start_minute)
        end = time(self.end_hour, self.end_minute)

        if start <= end:
            return start <= check_time <= end
        else:
            # Window crosses midnight
            return check_time >= start or check_time <= end


class JurisdictionRules(BaseModel):
    """Compliance rules for a specific jurisdiction."""
    jurisdiction_code: JurisdictionCode
    regulation_name: str
    consent_type_required: ConsentType
    time_window: TimeWindow
    opt_out_keywords: List[str] = Field(default_factory=list)
    disclosure_required: bool = Field(default=False)
    disclosure_text: str = ""
    ai_disclosure_required: bool = Field(default=False)
    recording_consent_required: bool = Field(default=False)
    data_residency_required: bool = Field(default=False)
    max_contacts_per_day: int = Field(default=3)
    do_not_call_list_mandatory: bool = Field(default=True)
    retention_days: int = Field(default=365)

    model_config = ConfigDict(use_enum_values=True)


class JurisdictionResult(BaseModel):
    """Result from jurisdiction compliance check."""
    jurisdiction: JurisdictionCode
    is_compliant: bool = True
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    rules_applied: Dict[str, Any] = Field(default_factory=dict)
    consent_required: ConsentType = ConsentType.NONE_REQUIRED
    allowed_time: bool = True
    processing_time_ms: float = Field(default=0.0)

    model_config = ConfigDict(use_enum_values=True)


# Default rules per jurisdiction
DEFAULT_JURISDICTION_RULES: Dict[JurisdictionCode, JurisdictionRules] = {
    JurisdictionCode.US: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.US,
        regulation_name="TCPA (Telephone Consumer Protection Act)",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=8, end_hour=21),  # 8AM - 9PM local
        opt_out_keywords=["STOP", "QUIT", "CANCEL", "UNSUBSCRIBE", "END"],
        disclosure_required=True,
        disclosure_text="This call is being recorded for quality and training purposes.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=False,
        max_contacts_per_day=3,
        do_not_call_list_mandatory=True,
        retention_days=2555,  # 7 years
    ),
    JurisdictionCode.EU: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.EU,
        regulation_name="GDPR (General Data Protection Regulation)",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=8, end_hour=21),
        opt_out_keywords=["STOP", "UNSUBSCRIBE", "OPTOUT", "OPT-OUT"],
        disclosure_required=True,
        disclosure_text="This communication is processed in accordance with GDPR.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=True,
        max_contacts_per_day=2,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
    JurisdictionCode.UK: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.UK,
        regulation_name="UK GDPR / PECR",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=8, end_hour=21),
        opt_out_keywords=["STOP", "UNSUBSCRIBE", "OPTOUT"],
        disclosure_required=True,
        disclosure_text="This communication is processed in accordance with UK GDPR.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=True,
        max_contacts_per_day=2,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
    JurisdictionCode.IN: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.IN,
        regulation_name="DPDPA (Digital Personal Data Protection Act)",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=9, end_hour=21),  # 9AM - 9PM IST
        opt_out_keywords=["STOP", "नहीं", "CANCEL", "UNSUBSCRIBE"],
        disclosure_required=True,
        disclosure_text="This communication is in compliance with DPDPA.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=True,
        max_contacts_per_day=3,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
    JurisdictionCode.CA: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.CA,
        regulation_name="CASL (Canada Anti-Spam Legislation)",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=8, end_hour=21),
        opt_out_keywords=["STOP", "UNSUBSCRIBE", "OPTOUT"],
        disclosure_required=True,
        disclosure_text="This communication complies with CASL.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=False,
        max_contacts_per_day=2,
        do_not_call_list_mandatory=True,
        retention_days=2555,
    ),
    JurisdictionCode.AU: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.AU,
        regulation_name="Spam Act 2003",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=8, end_hour=20),  # 8AM - 8PM
        opt_out_keywords=["STOP", "UNSUBSCRIBE", "OPTOUT"],
        disclosure_required=True,
        disclosure_text="This communication complies with Spam Act 2003.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=False,
        max_contacts_per_day=3,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
    JurisdictionCode.SG: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.SG,
        regulation_name="PDPA (Personal Data Protection Act)",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=9, end_hour=21),
        opt_out_keywords=["STOP", "UNSUBSCRIBE", "OPTOUT"],
        disclosure_required=True,
        disclosure_text="This communication complies with PDPA.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=False,
        max_contacts_per_day=3,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
    JurisdictionCode.JP: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.JP,
        regulation_name="APPI (Act on Protection of Personal Information)",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=9, end_hour=21),
        opt_out_keywords=["STOP", "配信停止", "UNSUBSCRIBE"],
        disclosure_required=True,
        disclosure_text="This communication complies with APPI.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=True,
        max_contacts_per_day=2,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
    JurisdictionCode.BR: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.BR,
        regulation_name="LGPD (Lei Geral de Protecao de Dados)",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=8, end_hour=21),
        opt_out_keywords=["STOP", "CANCELAR", "UNSUBSCRIBE"],
        disclosure_required=True,
        disclosure_text="This communication complies with LGPD.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=True,
        max_contacts_per_day=3,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
    JurisdictionCode.OTHER: JurisdictionRules(
        jurisdiction_code=JurisdictionCode.OTHER,
        regulation_name="General Compliance",
        consent_type_required=ConsentType.EXPRESS_WRITTEN,
        time_window=TimeWindow(start_hour=8, end_hour=21),
        opt_out_keywords=["STOP", "UNSUBSCRIBE", "CANCEL"],
        disclosure_required=True,
        disclosure_text="This communication is processed in compliance with applicable laws.",
        ai_disclosure_required=True,
        recording_consent_required=True,
        data_residency_required=False,
        max_contacts_per_day=2,
        do_not_call_list_mandatory=True,
        retention_days=365,
    ),
}


class JurisdictionManager:
    """
    Jurisdiction Manager for PARWA Compliance.

    Provides jurisdiction-specific compliance rules and checks
    for customer communications across different regions.

    Features:
    - Jurisdiction detection from country codes
    - Compliance rule enforcement
    - Time window validation
    - Consent requirement checks
    """

    def __init__(
        self,
        custom_rules: Optional[Dict[JurisdictionCode, JurisdictionRules]] = None
    ) -> None:
        """
        Initialize Jurisdiction Manager.

        Args:
            custom_rules: Optional custom rules to override defaults
        """
        self._rules = DEFAULT_JURISDICTION_RULES.copy()
        if custom_rules:
            self._rules.update(custom_rules)

        # Performance tracking
        self._checks_performed = 0
        self._violations_detected = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "jurisdiction_manager_initialized",
            "jurisdictions_configured": len(self._rules),
        })

    def get_rules(self, jurisdiction: JurisdictionCode) -> JurisdictionRules:
        """
        Get compliance rules for a jurisdiction.

        Args:
            jurisdiction: Jurisdiction code

        Returns:
            JurisdictionRules for the jurisdiction
        """
        return self._rules.get(jurisdiction, self._rules[JurisdictionCode.OTHER])

    def detect_jurisdiction(
        self,
        country_code: Optional[str] = None,
        phone_number: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> JurisdictionCode:
        """
        Detect jurisdiction from available signals.

        Args:
            country_code: ISO country code (e.g., "US", "IN")
            phone_number: Phone number with country code
            ip_address: IP address for geolocation

        Returns:
            Detected JurisdictionCode
        """
        # Priority: explicit country code > phone prefix > IP

        if country_code:
            code = country_code.upper().strip()
            try:
                return JurisdictionCode(code)
            except ValueError:
                pass

        # Phone number country detection
        if phone_number:
            prefix = self._extract_country_prefix(phone_number)
            if prefix:
                return self._prefix_to_jurisdiction(prefix)

        # Default to OTHER
        return JurisdictionCode.OTHER

    def check_compliance(
        self,
        jurisdiction: JurisdictionCode,
        communication_type: CommunicationType,
        has_consent: bool = False,
        consent_type: Optional[ConsentType] = None,
        check_time: Optional[time] = None,
        contacts_today: int = 0,
        is_on_dnc_list: bool = False
    ) -> JurisdictionResult:
        """
        Check compliance for a communication attempt.

        Args:
            jurisdiction: Target jurisdiction
            communication_type: Type of communication
            has_consent: Whether consent exists
            consent_type: Type of consent obtained
            check_time: Time to check (defaults to now)
            contacts_today: Number of contacts already made today
            is_on_dnc_list: Whether recipient is on Do Not Call list

        Returns:
            JurisdictionResult with compliance status
        """
        start_time = datetime.now()
        rules = self.get_rules(jurisdiction)

        result = JurisdictionResult(
            jurisdiction=jurisdiction,
            consent_required=rules.consent_type_required,
        )

        violations = []
        warnings = []

        # Check Do Not Call list
        if is_on_dnc_list and rules.do_not_call_list_mandatory:
            violations.append("Recipient is on Do Not Call list")

        # Check consent requirements
        consent_required_val = (
            rules.consent_type_required.value
            if isinstance(rules.consent_type_required, ConsentType)
            else rules.consent_type_required
        )
        if rules.consent_type_required != ConsentType.NONE_REQUIRED:
            if not has_consent:
                violations.append(
                    f"Consent required ({consent_required_val}) but not obtained"
                )
            elif consent_type and not self._is_consent_sufficient(
                consent_type, rules.consent_type_required
            ):
                warnings.append(
                    f"Consent type ({consent_type.value}) may not meet "
                    f"requirement ({consent_required_val})"
                )

        # Check time window
        if check_time is None:
            check_time = datetime.now().time()

        result.allowed_time = rules.time_window.is_within_window(check_time)
        if not result.allowed_time:
            violations.append(
                f"Time {check_time.strftime('%H:%M')} outside allowed window "
                f"({rules.time_window.start_hour}:00 - {rules.time_window.end_hour}:00)"
            )

        # Check contact frequency
        if contacts_today >= rules.max_contacts_per_day:
            violations.append(
                f"Maximum daily contacts ({rules.max_contacts_per_day}) exceeded"
            )

        # Build result
        result.violations = violations
        result.warnings = warnings
        result.is_compliant = len(violations) == 0
        result.rules_applied = {
            "regulation": rules.regulation_name,
            "consent_type_required": consent_required_val,
            "time_window": {
                "start": f"{rules.time_window.start_hour}:00",
                "end": f"{rules.time_window.end_hour}:00",
            },
            "max_contacts_per_day": rules.max_contacts_per_day,
            "ai_disclosure_required": rules.ai_disclosure_required,
            "recording_consent_required": rules.recording_consent_required,
        }

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._checks_performed += 1
        if not result.is_compliant:
            self._violations_detected += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "jurisdiction_compliance_check",
            "jurisdiction": jurisdiction.value,
            "is_compliant": result.is_compliant,
            "violations_count": len(violations),
        })

        return result

    def get_disclosure_text(
        self,
        jurisdiction: JurisdictionCode,
        include_ai_disclosure: bool = True
    ) -> str:
        """
        Get required disclosure text for a jurisdiction.

        Args:
            jurisdiction: Target jurisdiction
            include_ai_disclosure: Whether to include AI disclosure

        Returns:
            Disclosure text string
        """
        rules = self.get_rules(jurisdiction)
        parts = []

        if rules.disclosure_required and rules.disclosure_text:
            parts.append(rules.disclosure_text)

        if include_ai_disclosure and rules.ai_disclosure_required:
            parts.append("You are speaking with an AI assistant.")

        return " ".join(parts) if parts else ""

    def get_opt_out_keywords(self, jurisdiction: JurisdictionCode) -> List[str]:
        """
        Get opt-out keywords for a jurisdiction.

        Args:
            jurisdiction: Target jurisdiction

        Returns:
            List of opt-out keywords
        """
        rules = self.get_rules(jurisdiction)
        return rules.opt_out_keywords.copy()

    def is_opt_out_message(
        self,
        message: str,
        jurisdiction: JurisdictionCode
    ) -> bool:
        """
        Check if a message is an opt-out request.

        Args:
            message: Message to check
            jurisdiction: Jurisdiction for keywords

        Returns:
            True if message contains opt-out keyword
        """
        keywords = self.get_opt_out_keywords(jurisdiction)
        message_upper = message.upper().strip()

        return any(keyword in message_upper for keyword in keywords)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get jurisdiction manager statistics.

        Returns:
            Dict with stats
        """
        return {
            "checks_performed": self._checks_performed,
            "violations_detected": self._violations_detected,
            "violation_rate": (
                self._violations_detected / self._checks_performed
                if self._checks_performed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._checks_performed
                if self._checks_performed > 0 else 0
            ),
        }

    def _extract_country_prefix(self, phone_number: str) -> Optional[str]:
        """Extract country calling code from phone number."""
        # Remove non-digits
        digits = "".join(c for c in phone_number if c.isdigit())

        # Common prefixes
        prefixes = {
            "1": "US",  # US/Canada
            "91": "IN",  # India
            "44": "UK",  # UK
            "81": "JP",  # Japan
            "61": "AU",  # Australia
            "55": "BR",  # Brazil
            "65": "SG",  # Singapore
        }

        # Check for matching prefixes
        for prefix_len in [2, 1]:
            if len(digits) >= prefix_len:
                prefix = digits[:prefix_len]
                if prefix in prefixes:
                    return prefixes[prefix]

        return None

    def _prefix_to_jurisdiction(self, prefix: str) -> JurisdictionCode:
        """Convert country prefix to jurisdiction code."""
        mapping = {
            "US": JurisdictionCode.US,
            "IN": JurisdictionCode.IN,
            "UK": JurisdictionCode.UK,
            "JP": JurisdictionCode.JP,
            "AU": JurisdictionCode.AU,
            "BR": JurisdictionCode.BR,
            "SG": JurisdictionCode.SG,
        }
        return mapping.get(prefix, JurisdictionCode.OTHER)

    def _is_consent_sufficient(
        self,
        obtained: ConsentType,
        required: ConsentType
    ) -> bool:
        """Check if obtained consent meets requirement."""
        hierarchy = {
            ConsentType.NONE_REQUIRED: 0,
            ConsentType.OPT_OUT: 1,
            ConsentType.IMPLIED: 2,
            ConsentType.EXPRESS_ORAL: 3,
            ConsentType.EXPRESS_WRITTEN: 4,
        }

        return hierarchy.get(obtained, 0) >= hierarchy.get(required, 0)


def get_jurisdiction_manager() -> JurisdictionManager:
    """
    Get a default JurisdictionManager instance.

    Returns:
        JurisdictionManager instance
    """
    return JurisdictionManager()
