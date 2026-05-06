"""
PARWA Webhook Malformation Handler.

Handles partially corrupted or malformed webhooks with graceful degradation.
Attempts to extract usable data from "half-corrupt" webhooks while logging
issues for debugging and compliance purposes.

Key Features:
- Graceful handling of partially corrupted JSON
- Field-level validation with fallback extraction
- Recovery strategies for common malformation patterns
- Comprehensive logging for audit trail
- Never fails silently - all issues are logged
"""
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from pydantic import BaseModel, Field, ValidationError

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MalformationType(str, Enum):
    """Types of webhook malformation."""
    TRUNCATED_JSON = "truncated_json"
    MISSING_FIELDS = "missing_fields"
    INVALID_FIELD_TYPES = "invalid_field_types"
    ENCODING_ERROR = "encoding_error"
    NULL_VALUES = "null_values"
    EXTRA_FIELDS = "extra_fields"
    PARTIAL_CORRUPTION = "partial_corruption"


class MalformationSeverity(str, Enum):
    """Severity levels for malformation."""
    LOW = "low"  # Can be recovered automatically
    MEDIUM = "medium"  # Partial recovery possible
    HIGH = "high"  # Minimal recovery, needs review
    CRITICAL = "critical"  # Unrecoverable


class MalformationReport(BaseModel):
    """Report of detected malformations."""
    malformation_type: MalformationType
    severity: MalformationSeverity
    field_name: Optional[str] = None
    original_value: Optional[str] = None
    recovered_value: Optional[Any] = None
    message: str
    recoverable: bool = True


class WebhookMalformationHandler:
    """
    Handler for processing malformed webhooks.
    
    Implements graceful degradation strategies to extract usable data
    from partially corrupted webhooks.
    """
    
    # Critical fields that must be present for processing
    SHOPIFY_ORDER_CRITICAL_FIELDS = ["id"]
    SHOPIFY_CUSTOMER_CRITICAL_FIELDS = ["id"]
    STRIPE_EVENT_CRITICAL_FIELDS = ["id", "type"]
    
    # Fields that can be recovered with defaults
    RECOVERABLE_FIELDS = {
        "email": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "currency": "USD",
        "status": "unknown",
        "financial_status": "unknown",
    }
    
    def __init__(
        self,
        strict_mode: bool = False,
        log_all_malformations: bool = True
    ) -> None:
        """
        Initialize Malformation Handler.
        
        Args:
            strict_mode: If True, reject any malformed webhooks
            log_all_malformations: If True, log all detected malformations
        """
        self.strict_mode = strict_mode
        self.log_all_malformations = log_all_malformations
    
    def process_shopify_webhook(
        self,
        raw_body: bytes,
        event_type: str
    ) -> Tuple[Optional[Dict[str, Any]], List[MalformationReport]]:
        """
        Process a Shopify webhook with malformation handling.
        
        Args:
            raw_body: Raw webhook body bytes
            event_type: Shopify event type (e.g., "orders/create")
            
        Returns:
            Tuple of (extracted_data, malformation_reports)
        """
        reports = []
        
        # Step 1: Attempt JSON parsing
        payload, parse_report = self._safe_json_parse(raw_body)
        if parse_report:
            reports.append(parse_report)
            
            if parse_report.severity == MalformationSeverity.CRITICAL:
                return None, reports
        
        if payload is None:
            return None, reports
        
        # Step 2: Validate and recover fields
        event_type_clean = event_type.replace("/", "_")
        
        if "order" in event_type_clean:
            validated, field_reports = self._validate_and_recover(
                payload,
                self.SHOPIFY_ORDER_CRITICAL_FIELDS,
                "shopify_order"
            )
        elif "customer" in event_type_clean:
            validated, field_reports = self._validate_and_recover(
                payload,
                self.SHOPIFY_CUSTOMER_CRITICAL_FIELDS,
                "shopify_customer"
            )
        else:
            validated, field_reports = payload, []
        
        reports.extend(field_reports)
        
        # Step 3: Log all malformations if enabled
        if self.log_all_malformations:
            self._log_malformations(reports, "shopify", event_type)
        
        # Step 4: Check strict mode
        if self.strict_mode and any(r.severity in [MalformationSeverity.HIGH, MalformationSeverity.CRITICAL] for r in reports):
            logger.warning({
                "event": "webhook_rejected_strict_mode",
                "source": "shopify",
                "event_type": event_type,
                "malformation_count": len(reports),
            })
            return None, reports
        
        return validated, reports
    
    def process_stripe_webhook(
        self,
        raw_body: bytes
    ) -> Tuple[Optional[Dict[str, Any]], List[MalformationReport]]:
        """
        Process a Stripe webhook with malformation handling.
        
        Args:
            raw_body: Raw webhook body bytes
            
        Returns:
            Tuple of (extracted_data, malformation_reports)
        """
        reports = []
        
        # Step 1: Attempt JSON parsing
        payload, parse_report = self._safe_json_parse(raw_body)
        if parse_report:
            reports.append(parse_report)
            
            if parse_report.severity == MalformationSeverity.CRITICAL:
                return None, reports
        
        if payload is None:
            return None, reports
        
        # Step 2: Validate and recover fields
        validated, field_reports = self._validate_and_recover(
            payload,
            self.STRIPE_EVENT_CRITICAL_FIELDS,
            "stripe_event"
        )
        reports.extend(field_reports)
        
        # Step 3: Log all malformations if enabled
        if self.log_all_malformations:
            self._log_malformations(reports, "stripe", payload.get("type", "unknown"))
        
        # Step 4: Check strict mode
        if self.strict_mode and any(r.severity in [MalformationSeverity.HIGH, MalformationSeverity.CRITICAL] for r in reports):
            logger.warning({
                "event": "webhook_rejected_strict_mode",
                "source": "stripe",
                "event_type": payload.get("type", "unknown"),
                "malformation_count": len(reports),
            })
            return None, reports
        
        return validated, reports
    
    def _safe_json_parse(
        self,
        raw_body: bytes
    ) -> Tuple[Optional[Dict[str, Any]], Optional[MalformationReport]]:
        """
        Safely parse JSON with recovery attempts.
        
        Args:
            raw_body: Raw bytes to parse
            
        Returns:
            Tuple of (parsed_dict, malformation_report_if_any)
        """
        # Try direct JSON parse first (with encoding error handling)
        try:
            return json.loads(raw_body), None
        except UnicodeDecodeError as e:
            logger.warning({
                "event": "unicode_decode_error",
                "error": str(e),
                "body_length": len(raw_body),
            })
            # Fall through to encoding recovery
        except json.JSONDecodeError as e:
            logger.warning({
                "event": "json_parse_error",
                "error": str(e),
                "position": e.pos,
                "body_length": len(raw_body),
            })
        
        # Recovery Strategy 1: Truncated JSON - try to close open brackets
        truncated = self._attempt_truncated_recovery(raw_body)
        if truncated:
            return truncated, MalformationReport(
                malformation_type=MalformationType.TRUNCATED_JSON,
                severity=MalformationSeverity.MEDIUM,
                message=f"JSON was truncated, recovered partial data",
                recoverable=True
            )
        
        # Recovery Strategy 2: Encoding issues - try different encodings
        for encoding in ["utf-8", "latin-1", "ascii"]:
            try:
                decoded = raw_body.decode(encoding, errors="replace")
                return json.loads(decoded), MalformationReport(
                    malformation_type=MalformationType.ENCODING_ERROR,
                    severity=MalformationSeverity.LOW,
                    message=f"Recovered from encoding error using {encoding}",
                    recoverable=True
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        
        # Recovery Strategy 3: Extract what we can with regex
        extracted = self._extract_fields_with_regex(raw_body)
        if extracted:
            return extracted, MalformationReport(
                malformation_type=MalformationType.PARTIAL_CORRUPTION,
                severity=MalformationSeverity.HIGH,
                message="JSON severely corrupted, extracted fields with regex",
                recoverable=True
            )
        
        # Unrecoverable
        return None, MalformationReport(
            malformation_type=MalformationType.PARTIAL_CORRUPTION,
            severity=MalformationSeverity.CRITICAL,
            message="JSON completely unrecoverable",
            recoverable=False
        )
    
    def _attempt_truncated_recovery(
        self,
        raw_body: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to recover truncated JSON by closing open brackets.
        
        Args:
            raw_body: Raw bytes that failed to parse
            
        Returns:
            Recovered dict or None
        """
        try:
            text = raw_body.decode("utf-8", errors="replace")
            
            # Count open/close brackets
            open_curly = text.count("{")
            close_curly = text.count("}")
            open_square = text.count("[")
            close_square = text.count("]")
            
            # Add missing closing brackets
            text += "]" * (open_square - close_square)
            text += "}" * (open_curly - close_curly)
            
            return json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    
    def _extract_fields_with_regex(
        self,
        raw_body: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Extract known fields using regex patterns.
        
        Args:
            raw_body: Raw bytes to extract from
            
        Returns:
            Dict with extracted fields or None
        """
        try:
            text = raw_body.decode("utf-8", errors="replace")
            extracted = {}
            
            # Common field patterns
            patterns = {
                "id": r'"id"\s*:\s*(\d+)',
                "email": r'"email"\s*:\s*"([^"]+)"',
                "type": r'"type"\s*:\s*"([^"]+)"',
                "customer_id": r'"customer_id"\s*:\s*"([^"]+)"',
                "amount": r'"amount"\s*:\s*(\d+)',
            }
            
            for field, pattern in patterns.items():
                match = re.search(pattern, text)
                if match:
                    extracted[field] = match.group(1)
            
            return extracted if extracted else None
        except Exception:
            return None
    
    def _validate_and_recover(
        self,
        payload: Dict[str, Any],
        critical_fields: List[str],
        context: str
    ) -> Tuple[Dict[str, Any], List[MalformationReport]]:
        """
        Validate payload and recover missing fields where possible.
        
        Args:
            payload: Parsed payload dict
            critical_fields: Fields that must be present
            context: Context for logging (e.g., "shopify_order")
            
        Returns:
            Tuple of (validated_payload, malformation_reports)
        """
        reports = []
        validated = dict(payload)
        
        # Check for missing critical fields
        for field in critical_fields:
            if field not in payload or payload[field] is None:
                reports.append(MalformationReport(
                    malformation_type=MalformationType.MISSING_FIELDS,
                    severity=MalformationSeverity.CRITICAL,
                    field_name=field,
                    message=f"Critical field '{field}' is missing",
                    recoverable=False
                ))
        
        # Check for missing recoverable fields
        for field, default in self.RECOVERABLE_FIELDS.items():
            if field not in validated or validated[field] is None:
                if field in payload:
                    # Field exists but is null
                    validated[field] = default
                    reports.append(MalformationReport(
                        malformation_type=MalformationType.NULL_VALUES,
                        severity=MalformationSeverity.LOW,
                        field_name=field,
                        original_value="null",
                        recovered_value=str(default),
                        message=f"Null value for '{field}' replaced with default",
                        recoverable=True
                    ))
        
        # Check for type mismatches
        type_validations = {
            "id": (int, str),
            "amount": (int, float),
            "email": str,
            "created_at": str,
        }
        
        for field, expected_types in type_validations.items():
            if field in validated and validated[field] is not None:
                if not isinstance(validated[field], expected_types):
                    # Attempt type conversion
                    try:
                        if expected_types == (int, str) or expected_types == int:
                            validated[field] = int(validated[field])
                        elif expected_types == (int, float):
                            validated[field] = float(validated[field])
                        elif expected_types == str:
                            validated[field] = str(validated[field])
                        
                        reports.append(MalformationReport(
                            malformation_type=MalformationType.INVALID_FIELD_TYPES,
                            severity=MalformationSeverity.LOW,
                            field_name=field,
                            original_value=str(payload[field]),
                            recovered_value=str(validated[field]),
                            message=f"Type conversion applied to '{field}'",
                            recoverable=True
                        ))
                    except (ValueError, TypeError):
                        reports.append(MalformationReport(
                            malformation_type=MalformationType.INVALID_FIELD_TYPES,
                            severity=MalformationSeverity.MEDIUM,
                            field_name=field,
                            original_value=str(payload[field]),
                            message=f"Cannot convert '{field}' to expected type",
                            recoverable=False
                        ))
        
        return validated, reports
    
    def _log_malformations(
        self,
        reports: List[MalformationReport],
        source: str,
        event_type: str
    ) -> None:
        """
        Log all malformation reports.
        
        Args:
            reports: List of malformation reports
            source: Webhook source (shopify, stripe)
            event_type: Event type
        """
        for report in reports:
            log_data = {
                "event": "webhook_malformation_detected",
                "source": source,
                "event_type": event_type,
                "malformation_type": report.malformation_type.value,
                "severity": report.severity.value,
                "field_name": report.field_name,
                "message": report.message,
                "recoverable": report.recoverable,
            }
            
            if report.severity in [MalformationSeverity.HIGH, MalformationSeverity.CRITICAL]:
                logger.error(log_data)
            else:
                logger.warning(log_data)


def create_malformation_handler(
    strict_mode: bool = False
) -> WebhookMalformationHandler:
    """
    Factory function to create a Malformation Handler.
    
    Args:
        strict_mode: If True, reject any malformed webhooks
        
    Returns:
        Configured WebhookMalformationHandler
    """
    return WebhookMalformationHandler(strict_mode=strict_mode)
