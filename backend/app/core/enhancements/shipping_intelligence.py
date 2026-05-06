"""
Shipping Intelligence Engine — Multi-Carrier Integration + Proactive Delay Notifications.

Improvement Target: Shipping/Logistics 83% → 88% automation.

Components:
  1. Multi-Carrier Tracker: Simulated multi-carrier tracking integration
     that can query shipment status from multiple carriers (FedEx, UPS,
     DHL, USPS, etc.) and consolidate tracking information.
  2. Proactive Delay Notifier: Detects delayed shipments and generates
     proactive notifications to customers before they complain. Includes
     delay reason classification, revised ETA, and compensation offers.
  3. Shipping Issue Resolver: Automated resolution of common shipping
     issues (wrong address, missed delivery, damaged package, lost package)
     with appropriate actions (reorder, refund, investigation).

Architecture:
  Called from smart_enrichment node to enrich shipping context and detect
  delays. Called from auto_action node to trigger proactive notifications
  and shipping resolution actions.

BC-001: company_id first parameter on public methods.
BC-008: Every method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("shipping_intelligence")


# ══════════════════════════════════════════════════════════════════
# CARRIER CONFIGURATION
# ══════════════════════════════════════════════════════════════════

CARRIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "fedex": {
        "name": "FedEx",
        "tracking_pattern": r'\b\d{12,15}\b',
        "tracking_url": "https://www.fedex.com/fedextrack/?trknbr={tracking_number}",
        "status_map": {
            "in_transit": "In Transit",
            "out_for_delivery": "Out for Delivery",
            "delivered": "Delivered",
            "exception": "Delivery Exception",
        },
    },
    "ups": {
        "name": "UPS",
        "tracking_pattern": r'\b1Z[A-Z0-9]{16}\b',
        "tracking_url": "https://www.ups.com/track?tracknum={tracking_number}",
        "status_map": {
            "in_transit": "In Transit",
            "out_for_delivery": "Out for Delivery",
            "delivered": "Delivered",
            "exception": "Exception",
        },
    },
    "dhl": {
        "name": "DHL",
        "tracking_pattern": r'\b\d{10}\b',
        "tracking_url": "https://www.dhl.com/en/express/tracking.html?AWB={tracking_number}",
        "status_map": {
            "in_transit": "In Transit",
            "out_for_delivery": "Out for Delivery",
            "delivered": "Delivered",
            "exception": "Exception",
        },
    },
    "usps": {
        "name": "USPS",
        "tracking_pattern": r'\b(?:94|93|92|91|94)\d{20,22}\b',
        "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}",
        "status_map": {
            "in_transit": "In Transit",
            "out_for_delivery": "Out for Delivery",
            "delivered": "Delivered",
            "exception": "Exception",
        },
    },
}

# Shipping issue categories
SHIPPING_ISSUES: Dict[str, Dict[str, Any]] = {
    "delayed": {
        "keywords": [
            "late", "delayed", "not arrived", "hasn't arrived", "still waiting",
            "where is my order", "where is my package", "not delivered",
            "overdue", "past delivery date", "taking too long",
        ],
        "severity": "medium",
        "auto_resolvable": True,
        "resolution": "check_tracking_and_notify",
        "compensation": "shipping_refund_if_late",
    },
    "wrong_address": {
        "keywords": [
            "wrong address", "incorrect address", "wrong shipping address",
            "sent to wrong", "address change", "update address",
            "need to change address", "delivered to wrong",
        ],
        "severity": "high",
        "auto_resolvable": True,
        "resolution": "address_correction_or_reroute",
        "compensation": "free_reroute",
    },
    "missed_delivery": {
        "keywords": [
            "missed delivery", "wasn't home", "delivery attempt",
            "no one was home", "couldn't deliver", "left notice",
            "reschedule delivery", "need redelivery",
        ],
        "severity": "low",
        "auto_resolvable": True,
        "resolution": "reschedule_delivery",
        "compensation": None,
    },
    "damaged": {
        "keywords": [
            "damaged", "broken", "cracked", "dented", "torn",
            "destroyed", "ruined", "arrived damaged", "package damaged",
            "item broken", "not in good condition",
        ],
        "severity": "high",
        "auto_resolvable": True,
        "resolution": "replacement_or_refund",
        "compensation": "full_refund_or_replacement",
    },
    "lost": {
        "keywords": [
            "lost", "never arrived", "can't find", "missing package",
            "tracking not updating", "no tracking updates", "disappeared",
            "stolen", "porch pirate",
        ],
        "severity": "critical",
        "auto_resolvable": True,
        "resolution": "investigate_and_replace_or_refund",
        "compensation": "full_refund_or_replacement_plus_credit",
    },
    "wrong_item": {
        "keywords": [
            "wrong item", "incorrect item", "received wrong", "not what i ordered",
            "different product", "wrong size", "wrong color",
            "received someone else's order",
        ],
        "severity": "high",
        "auto_resolvable": True,
        "resolution": "return_wrong_send_correct",
        "compensation": "free_return_and_replacement",
    },
}

# Delay reason classifications
DELAY_REASONS: Dict[str, Dict[str, Any]] = {
    "weather": {
        "keywords": ["weather", "storm", "snow", "hurricane", "flood", "ice"],
        "customer_message": "due to severe weather conditions in the delivery area",
        "compensation_eligible": False,
    },
    "carrier_delay": {
        "keywords": ["carrier delay", "sorting facility", "facility issue", "operational"],
        "customer_message": "due to carrier operational delays",
        "compensation_eligible": True,
    },
    "customs": {
        "keywords": ["customs", "border", "international", "import", "duty"],
        "customer_message": "due to customs processing for international shipments",
        "compensation_eligible": False,
    },
    "high_volume": {
        "keywords": ["peak season", "holiday", "high volume", "busy period", "black friday"],
        "customer_message": "due to higher-than-normal shipment volume",
        "compensation_eligible": True,
    },
    "address_issue": {
        "keywords": ["address", "incomplete address", "missing suite", "apartment number"],
        "customer_message": "due to an address issue that needs clarification",
        "compensation_eligible": False,
    },
}


class ShippingIntelligenceEngine:
    """Shipping Intelligence Engine for logistics and tracking automation.

    Provides:
      - Multi-carrier tracking number detection
      - Shipping issue classification
      - Proactive delay notification generation
      - Automated shipping resolution actions

    Usage:
        engine = ShippingIntelligenceEngine()
        tracking = engine.detect_tracking_number(query)
        issue = engine.classify_shipping_issue(query)
        delay = engine.assess_delay(issue)
        actions = engine.get_shipping_actions(issue, delay)
    """

    def __init__(self) -> None:
        """Initialize the shipping intelligence engine."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        try:
            for issue_id, config in SHIPPING_ISSUES.items():
                patterns = []
                for kw in config["keywords"]:
                    if " " in kw:
                        patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
                    else:
                        patterns.append(re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE))
                self._compiled_patterns[issue_id] = patterns

            for reason_id, config in DELAY_REASONS.items():
                patterns = []
                for kw in config["keywords"]:
                    patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
                if not self._compiled_patterns.get(reason_id):
                    self._compiled_patterns[reason_id] = patterns
                else:
                    self._compiled_patterns[reason_id].extend(patterns)

        except Exception:
            logger.exception("shipping_pattern_compilation_failed")

    def detect_tracking_number(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """Detect tracking numbers in the customer query.

        Args:
            query: Customer's raw message.

        Returns:
            Tracking detection dict:
              - tracking_detected: bool
              - tracking_numbers: List[Dict] (carrier, number, url)
              - primary_carrier: str
        """
        try:
            if not query:
                return {"tracking_detected": False, "tracking_numbers": [], "primary_carrier": ""}

            detected: List[Dict[str, Any]] = []

            for carrier_id, config in CARRIER_CONFIG.items():
                pattern = re.compile(config["tracking_pattern"], re.IGNORECASE)
                matches = pattern.findall(query)

                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    if match:
                        detected.append({
                            "carrier": config["name"],
                            "carrier_id": carrier_id,
                            "tracking_number": match,
                            "tracking_url": config["tracking_url"].format(tracking_number=match),
                        })

            return {
                "tracking_detected": len(detected) > 0,
                "tracking_numbers": detected,
                "primary_carrier": detected[0]["carrier"] if detected else "",
            }

        except Exception:
            logger.exception("tracking_detection_failed")
            return {"tracking_detected": False, "tracking_numbers": [], "primary_carrier": ""}

    def classify_shipping_issue(
        self,
        query: str,
        classification: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Classify the type of shipping issue from the customer query.

        Args:
            query: Customer's raw message.
            classification: Classification result.

        Returns:
            Shipping issue dict:
              - issue_detected: bool
              - issue_type: str
              - severity: str
              - auto_resolvable: bool
              - resolution: str
              - compensation: Optional[str]
              - confidence: float
        """
        try:
            if not query:
                return self._default_issue()

            query_lower = query.lower()

            best_issue = None
            best_confidence = 0.0
            best_match_count = 0

            for issue_id, patterns in self._compiled_patterns.items():
                if issue_id in DELAY_REASONS:
                    continue  # Skip delay reason patterns

                match_count = 0
                for pattern in patterns:
                    if pattern.search(query_lower):
                        match_count += 1

                if match_count > 0:
                    confidence = min(1.0, match_count * 0.25 + 0.4)
                    if match_count > best_match_count:
                        best_issue = issue_id
                        best_confidence = confidence
                        best_match_count = match_count

            if best_issue and best_confidence >= 0.3:
                issue_config = SHIPPING_ISSUES[best_issue]
                return {
                    "issue_detected": True,
                    "issue_type": best_issue,
                    "severity": issue_config.get("severity", "medium"),
                    "auto_resolvable": issue_config.get("auto_resolvable", False),
                    "resolution": issue_config.get("resolution", "manual_review"),
                    "compensation": issue_config.get("compensation"),
                    "confidence": round(best_confidence, 3),
                }

            return self._default_issue()

        except Exception:
            logger.exception("shipping_issue_classification_failed")
            return self._default_issue()

    def assess_delay(
        self,
        shipping_issue: Dict[str, Any],
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assess shipping delay and generate proactive notification.

        Args:
            shipping_issue: Output from classify_shipping_issue().
            query: Customer's raw message (optional, for delay reason detection).

        Returns:
            Delay assessment dict:
              - delay_detected: bool
              - delay_reason: str
              - customer_message: str
              - compensation_eligible: bool
              - recommended_actions: List[str]
              - notification_template: str
        """
        try:
            issue_type = shipping_issue.get("issue_type", "")

            if issue_type not in ("delayed", "lost"):
                return self._default_delay()

            # Try to determine delay reason
            delay_reason = "carrier_delay"  # Default
            query_lower = (query or "").lower()

            for reason_id, config in DELAY_REASONS.items():
                for kw in config["keywords"]:
                    if kw in query_lower:
                        delay_reason = reason_id
                        break

            reason_config = DELAY_REASONS.get(delay_reason, DELAY_REASONS["carrier_delay"])

            # Generate notification template
            notification = (
                "We've detected a delay with your shipment. "
                f"This is {reason_config['customer_message']}. "
            )

            if reason_config["compensation_eligible"]:
                notification += (
                    "Since this delay is on our end, we'd like to offer you "
                    "a shipping refund or credit toward your next order. "
                )

            notification += (
                "We're actively monitoring your package and will send you "
                "an update as soon as there's a change in status."
            )

            # Recommended actions
            recommended = ["send_proactive_notification", "monitor_tracking"]
            if reason_config["compensation_eligible"]:
                recommended.append("offer_shipping_compensation")
            if issue_type == "lost":
                recommended.extend(["initiate_carrier_investigation", "offer_replacement_or_refund"])

            return {
                "delay_detected": True,
                "delay_reason": delay_reason,
                "customer_message": reason_config["customer_message"],
                "compensation_eligible": reason_config["compensation_eligible"],
                "recommended_actions": recommended,
                "notification_template": notification,
            }

        except Exception:
            logger.exception("delay_assessment_failed")
            return self._default_delay()

    def get_shipping_actions(
        self,
        shipping_issue: Dict[str, Any],
        delay_assessment: Dict[str, Any],
        tracking_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get automated shipping resolution actions.

        Args:
            shipping_issue: Output from classify_shipping_issue().
            delay_assessment: Output from assess_delay().
            tracking_info: Output from detect_tracking_number().

        Returns:
            List of action dicts for auto_action node.
        """
        try:
            actions: List[Dict[str, Any]] = []
            issue_type = shipping_issue.get("issue_type", "")
            severity = shipping_issue.get("severity", "medium")

            # Proactive delay notification
            if delay_assessment.get("delay_detected"):
                actions.append({
                    "action_type": "send_proactive_delay_notification",
                    "action_data": {
                        "notification_template": delay_assessment.get("notification_template", ""),
                        "delay_reason": delay_assessment.get("delay_reason", "unknown"),
                        "compensation_eligible": delay_assessment.get("compensation_eligible", False),
                    },
                    "priority": "high" if severity in ("high", "critical") else "medium",
                    "automated": True,
                })

            # Compensation for eligible delays
            if delay_assessment.get("compensation_eligible"):
                actions.append({
                    "action_type": "apply_shipping_compensation",
                    "action_data": {
                        "compensation_type": "shipping_refund",
                        "issue_type": issue_type,
                    },
                    "priority": "medium",
                    "automated": True,
                })

            # Issue-specific actions
            resolution = shipping_issue.get("resolution", "")
            if resolution == "check_tracking_and_notify":
                actions.append({
                    "action_type": "track_shipment",
                    "action_data": {
                        "tracking_numbers": tracking_info.get("tracking_numbers", []),
                        "carrier": tracking_info.get("primary_carrier", ""),
                    },
                    "priority": "medium",
                    "automated": True,
                })

            elif resolution == "reschedule_delivery":
                actions.append({
                    "action_type": "schedule_redelivery",
                    "action_data": {"issue_type": issue_type},
                    "priority": "low",
                    "automated": True,
                })

            elif resolution in ("replacement_or_refund", "investigate_and_replace_or_refund"):
                actions.append({
                    "action_type": "initiate_replacement_or_refund",
                    "action_data": {
                        "issue_type": issue_type,
                        "compensation": shipping_issue.get("compensation"),
                        "severity": severity,
                    },
                    "priority": "high",
                    "automated": True,
                })

            elif resolution == "address_correction_or_reroute":
                actions.append({
                    "action_type": "initiate_address_correction",
                    "action_data": {"issue_type": issue_type},
                    "priority": "high",
                    "automated": True,
                })

            elif resolution == "return_wrong_send_correct":
                actions.append({
                    "action_type": "initiate_exchange",
                    "action_data": {
                        "issue_type": issue_type,
                        "return_required": True,
                    },
                    "priority": "high",
                    "automated": True,
                })

            # Lost package investigation
            if issue_type == "lost":
                actions.append({
                    "action_type": "initiate_carrier_investigation",
                    "action_data": {
                        "tracking_numbers": tracking_info.get("tracking_numbers", []),
                        "carrier": tracking_info.get("primary_carrier", ""),
                    },
                    "priority": "critical",
                    "automated": True,
                })

            return actions

        except Exception:
            logger.exception("shipping_action_generation_failed")
            return []

    def generate_shipping_context(
        self,
        shipping_issue: Dict[str, Any],
        delay_assessment: Dict[str, Any],
        tracking_info: Dict[str, Any],
    ) -> str:
        """Generate shipping context prompt addition for the LLM.

        Args:
            shipping_issue: Output from classify_shipping_issue().
            delay_assessment: Output from assess_delay().
            tracking_info: Output from detect_tracking_number().

        Returns:
            Prompt string to append to generation system prompt.
        """
        try:
            parts: List[str] = []

            issue_type = shipping_issue.get("issue_type", "")
            if issue_type:
                resolution = shipping_issue.get("resolution", "").replace("_", " ")
                compensation = shipping_issue.get("compensation")
                parts.append(
                    f"The customer has a shipping issue: {issue_type.replace('_', ' ')}. "
                    f"The recommended resolution is: {resolution}. "
                )
                if compensation:
                    parts.append(
                        f"Eligible compensation: {compensation.replace('_', ' ')}. "
                        f"Proactively offer this to the customer. "
                    )

            if delay_assessment.get("delay_detected"):
                reason = delay_assessment.get("delay_reason", "unknown")
                parts.append(
                    f"A shipping delay has been detected, reason: {reason.replace('_', ' ')}. "
                    f"Acknowledge the delay and provide the customer with updated expectations. "
                )

            if tracking_info.get("tracking_detected"):
                carrier = tracking_info.get("primary_carrier", "")
                parts.append(
                    f"A tracking number for {carrier} was detected. "
                    f"Reference the carrier name and offer to help track the package. "
                )

            return " ".join(parts) if parts else ""

        except Exception:
            return ""

    def query_carrier_data(
        self,
        tracking_info: Dict[str, Any],
        shipping_issue: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Simulate multi-carrier API integration to get shipping data.

        Args:
            tracking_info: Output from detect_tracking_number().
            shipping_issue: Output from classify_shipping_issue().

        Returns:
            Carrier data dict:
              - carrier: str
              - tracking_status: str
              - estimated_delivery: str
              - carrier_api_called: bool
              - last_update: str
        """
        try:
            from datetime import datetime, timezone, timedelta

            carrier = tracking_info.get("primary_carrier", "")
            tracking_numbers = tracking_info.get("tracking_numbers", [])
            issue_type = shipping_issue.get("issue_type", "")

            api_called = bool(tracking_numbers)

            # Simulate carrier status based on issue type
            if issue_type == "delayed":
                status = "delayed"
                eta = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
            elif issue_type == "lost":
                status = "exception"
                eta = "unknown"
            elif issue_type == "damaged":
                status = "delivered_damaged"
                eta = "delivered"
            elif issue_type == "wrong_address":
                status = "address_exception"
                eta = "pending_correction"
            elif issue_type == "missed_delivery":
                status = "delivery_attempted"
                eta = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
            elif tracking_numbers:
                status = "in_transit"
                eta = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
            else:
                status = "no_tracking_available"
                eta = "unknown"

            return {
                "carrier": carrier,
                "tracking_status": status,
                "estimated_delivery": eta,
                "carrier_api_called": api_called,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            logger.exception("carrier_data_query_failed")
            return {
                "carrier": "",
                "tracking_status": "unknown",
                "estimated_delivery": "unknown",
                "carrier_api_called": False,
                "last_update": "",
            }

    def generate_delay_notification(
        self,
        shipping_issue: Dict[str, Any],
        delay_assessment: Dict[str, Any],
        carrier_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate proactive delay notification for the customer.

        Args:
            shipping_issue: Output from classify_shipping_issue().
            delay_assessment: Output from assess_delay().
            carrier_data: Output from query_carrier_data().

        Returns:
            Delay notification dict:
              - notification_sent: bool
              - notification_type: str
              - delay_reason: str
              - revised_eta: str
              - compensation_offered: bool
        """
        try:
            issue_type = shipping_issue.get("issue_type", "")
            delay_detected = delay_assessment.get("delay_detected", False)
            compensation_eligible = delay_assessment.get("compensation_eligible", False)
            delay_reason = delay_assessment.get("delay_reason", "unknown")

            # Determine notification type
            if issue_type == "lost":
                notification_type = "lost_package_alert"
            elif issue_type == "delayed":
                notification_type = "delay_notification"
            elif delay_detected:
                notification_type = "proactive_delay_alert"
            else:
                notification_type = "status_update"

            # Notification should be sent for delays and lost packages
            should_send = delay_detected or issue_type in ("delayed", "lost")

            # Revised ETA from carrier data
            revised_eta = carrier_data.get("estimated_delivery", "unknown")

            return {
                "notification_sent": should_send,
                "notification_type": notification_type,
                "delay_reason": delay_reason,
                "revised_eta": revised_eta,
                "compensation_offered": compensation_eligible,
            }
        except Exception:
            logger.exception("delay_notification_generation_failed")
            return {
                "notification_sent": False,
                "notification_type": "none",
                "delay_reason": "unknown",
                "revised_eta": "unknown",
                "compensation_offered": False,
            }

    def _default_issue(self) -> Dict[str, Any]:
        """Return default no-issue result."""
        return {
            "issue_detected": False,
            "issue_type": "",
            "severity": "low",
            "auto_resolvable": False,
            "resolution": "",
            "compensation": None,
            "confidence": 0.0,
        }

    def _default_delay(self) -> Dict[str, Any]:
        """Return default no-delay result."""
        return {
            "delay_detected": False,
            "delay_reason": "",
            "customer_message": "",
            "compensation_eligible": False,
            "recommended_actions": [],
            "notification_template": "",
        }
