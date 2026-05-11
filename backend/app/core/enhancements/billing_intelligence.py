"""
Billing Intelligence Engine — Dispute Auto-Resolution + Anomaly Detection.

Improvement Target: Billing Inquiries 80% → 88% automation.

Components:
  1. Paddle Dispute Auto-Resolver: Automated resolution of common billing
     disputes (double charges, incorrect amounts, missing refunds, failed
     payments) using Paddle API integration.
  2. Billing Anomaly Detector: Detects billing anomalies by comparing
     current charges against expected patterns (subscription price,
     billing frequency, usage tiers).

Architecture:
  Called from smart_enrichment node to detect anomalies and assess
  dispute validity. Called from auto_action node to execute auto-
  resolution actions (refund initiation, credit application, etc.).

BC-001: company_id first parameter on public methods.
BC-008: Every method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("billing_intelligence")


# ══════════════════════════════════════════════════════════════════
# DISPUTE CATEGORIES AND RESOLUTION RULES
# ══════════════════════════════════════════════════════════════════

DISPUTE_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "double_charge": {
        "keywords": [
            "charged twice", "double charge", "duplicate charge",
            "charged two times", "billed twice", "two charges",
            "duplicate billing", "repeated charge",
        ],
        "auto_resolvable": True,
        "resolution": "refund_duplicate",
        "max_refund_percentage": 100,
        "priority": "high",
        "evidence_required": False,
    },
    "incorrect_amount": {
        "keywords": [
            "wrong amount", "incorrect charge", "overcharged",
            "charged too much", "price is wrong", "different price",
            "not what i agreed to", "more than expected",
        ],
        "auto_resolvable": True,
        "resolution": "adjust_charge",
        "max_refund_percentage": 100,
        "priority": "high",
        "evidence_required": True,
    },
    "missing_refund": {
        "keywords": [
            "refund not received", "where is my refund", "no refund",
            "haven't received refund", "refund pending", "refund delayed",
            "still waiting for refund", "refund not processed",
        ],
        "auto_resolvable": True,
        "resolution": "check_refund_status",
        "max_refund_percentage": 0,
        "priority": "medium",
        "evidence_required": False,
    },
    "unrecognized_charge": {
        "keywords": [
            "don't recognize", "unfamiliar charge", "didn't purchase",
            "never bought", "don't remember", "unknown charge",
            "fraudulent charge", "didn't authorize",
        ],
        "auto_resolvable": False,
        "resolution": "dispute_investigation",
        "max_refund_percentage": 100,
        "priority": "high",
        "evidence_required": True,
    },
    "failed_payment_retry": {
        "keywords": [
            "payment failed", "charge failed", "declined",
            "retry charge", "multiple attempts", "payment not going through",
            "card declined", "payment declined",
        ],
        "auto_resolvable": True,
        "resolution": "pause_retry_and_notify",
        "max_refund_percentage": 0,
        "priority": "medium",
        "evidence_required": False,
    },
    "subscription_price_change": {
        "keywords": [
            "price increase", "price changed", "new price",
            "different price than before", "more expensive now",
            "price went up", "wasn't notified of price change",
        ],
        "auto_resolvable": True,
        "resolution": "explain_price_change_or_grandfather",
        "max_refund_percentage": 50,
        "priority": "medium",
        "evidence_required": False,
    },
    "free_trial_charge": {
        "keywords": [
            "free trial", "shouldn't be charged", "trial period",
            "was supposed to be free", "charged during trial",
            "trial charge", "cancelled before trial ended",
        ],
        "auto_resolvable": True,
        "resolution": "verify_trial_and_refund_if_valid",
        "max_refund_percentage": 100,
        "priority": "high",
        "evidence_required": False,
    },
}

# Billing anomaly detection thresholds
ANOMALY_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "amount_deviation": {
        "description": "Charge amount deviates from expected by >20%",
        "threshold_pct": 20,
        "severity": "warning",
    },
    "frequency_deviation": {
        "description": "Billing frequency differs from subscription schedule",
        "threshold_days": 7,
        "severity": "warning",
    },
    "new_charge_type": {
        "description": "Charge type not in customer's subscription plan",
        "threshold": "any",
        "severity": "high",
    },
}


class BillingIntelligenceEngine:
    """Billing Intelligence Engine for dispute resolution and anomaly detection.

    Provides:
      - Dispute category detection and auto-resolution eligibility
      - Billing anomaly detection (amount, frequency, type)
      - Resolution action generation for Paddle integration
      - Self-service billing context generation

    Usage:
        engine = BillingIntelligenceEngine()
        dispute = engine.classify_dispute(query, classification)
        anomaly = engine.detect_anomaly(query, signals)
        actions = engine.get_resolution_actions(dispute, anomaly)
    """

    def __init__(self) -> None:
        """Initialize the billing intelligence engine."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        try:
            for category, config in DISPUTE_CATEGORIES.items():
                patterns = []
                for kw in config["keywords"]:
                    if " " in kw:
                        patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
                    else:
                        patterns.append(re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE))
                self._compiled_patterns[category] = patterns
        except Exception:
            logger.exception("billing_pattern_compilation_failed")

    def classify_dispute(
        self,
        query: str,
        classification: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Classify the billing dispute type and assess auto-resolution eligibility.

        Args:
            query: Customer's raw message.
            classification: Classification result (intent, confidence).

        Returns:
            Dispute classification dict:
              - dispute_category: str
              - auto_resolvable: bool
              - resolution_type: str
              - priority: str
              - evidence_required: bool
              - confidence: float
              - matched_keywords: List[str]
        """
        try:
            if not query:
                return self._default_dispute()

            query_lower = query.lower()

            best_category = "unknown"
            best_confidence = 0.0
            best_matches: List[str] = []

            for category, patterns in self._compiled_patterns.items():
                matches = []
                for pattern in patterns:
                    found = pattern.findall(query_lower)
                    if found:
                        matches.extend(found)

                if matches:
                    # More unique matches = higher confidence
                    confidence = min(1.0, len(set(matches)) * 0.3 + 0.4)
                    if confidence > best_confidence:
                        best_category = category
                        best_confidence = confidence
                        best_matches = list(set(matches))

            # Get dispute config
            dispute_config = DISPUTE_CATEGORIES.get(best_category, {})

            # Factor in classification intent
            if classification:
                intent = classification.get("intent", "")
                if intent == "billing" and best_confidence < 0.5:
                    best_confidence = max(best_confidence, 0.4)

            return {
                "dispute_category": best_category,
                "auto_resolvable": dispute_config.get("auto_resolvable", False),
                "resolution_type": dispute_config.get("resolution", "manual_review"),
                "priority": dispute_config.get("priority", "medium"),
                "evidence_required": dispute_config.get("evidence_required", False),
                "confidence": round(best_confidence, 3),
                "matched_keywords": best_matches,
                "max_refund_percentage": dispute_config.get("max_refund_percentage", 0),
            }

        except Exception:
            logger.exception("dispute_classification_failed")
            return self._default_dispute()

    def detect_anomaly(
        self,
        query: str,
        signals: Optional[Dict[str, Any]] = None,
        expected_amount: Optional[float] = None,
        actual_amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Detect billing anomalies by comparing against expected patterns.

        Args:
            query: Customer's raw message.
            signals: Extracted signals (may contain monetary_value).
            expected_amount: Expected subscription/charge amount.
            actual_amount: Actual charged amount.

        Returns:
            Anomaly detection dict:
              - anomaly_detected: bool
              - anomaly_types: List[str]
              - severity: str (none/low/medium/high)
              - details: Dict[str, Any]
              - recommendation: str
        """
        try:
            anomaly_types: List[str] = []
            details: Dict[str, Any] = {}
            severity = "none"

            # Check amount deviation
            if expected_amount is not None and actual_amount is not None and expected_amount > 0:
                deviation_pct = abs(actual_amount - expected_amount) / expected_amount * 100
                threshold = ANOMALY_THRESHOLDS["amount_deviation"]["threshold_pct"]

                if deviation_pct > threshold:
                    anomaly_types.append("amount_deviation")
                    details["amount_deviation_pct"] = round(deviation_pct, 2)
                    details["expected_amount"] = expected_amount
                    details["actual_amount"] = actual_amount
                    severity = "high" if deviation_pct > 50 else "medium"

            # Check for monetary value in signals
            if signals:
                monetary_value = signals.get("monetary_value", 0)
                if monetary_value > 0 and expected_amount and monetary_value != expected_amount:
                    anomaly_types.append("reported_amount_mismatch")
                    details["reported_amount"] = monetary_value
                    details["expected_amount"] = expected_amount

            # Check for anomaly indicators in query
            query_lower = query.lower() if query else ""
            anomaly_indicators = [
                "unexpected charge", "surprise charge", "random charge",
                "shouldn't have been charged", "didn't authorize",
            ]
            for indicator in anomaly_indicators:
                if indicator in query_lower:
                    anomaly_types.append("unexpected_charge_reported")
                    if severity == "none":
                        severity = "medium"
                    break

            return {
                "anomaly_detected": len(anomaly_types) > 0,
                "anomaly_types": anomaly_types,
                "severity": severity,
                "details": details,
                "recommendation": self._anomaly_recommendation(anomaly_types, severity),
            }

        except Exception:
            logger.exception("anomaly_detection_failed")
            return {
                "anomaly_detected": False,
                "anomaly_types": [],
                "severity": "none",
                "details": {},
                "recommendation": "proceed_with_standard_billing_flow",
            }

    def get_resolution_actions(
        self,
        dispute: Dict[str, Any],
        anomaly: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get automated billing resolution actions.

        Args:
            dispute: Output from classify_dispute().
            anomaly: Output from detect_anomaly().

        Returns:
            List of action dicts for auto_action node.
        """
        try:
            actions: List[Dict[str, Any]] = []

            auto_resolvable = dispute.get("auto_resolvable", False)
            resolution_type = dispute.get("resolution_type", "manual_review")
            priority = dispute.get("priority", "medium")
            dispute_category = dispute.get("dispute_category", "unknown")

            if auto_resolvable and dispute_category != "unknown":
                # Auto-resolution actions
                if resolution_type == "refund_duplicate":
                    actions.append({
                        "action_type": "initiate_refund",
                        "action_data": {
                            "reason": "duplicate_charge",
                            "refund_percentage": dispute.get("max_refund_percentage", 100),
                            "auto_approved": True,
                        },
                        "priority": priority,
                        "automated": True,
                    })

                elif resolution_type == "check_refund_status":
                    actions.append({
                        "action_type": "check_refund_status",
                        "action_data": {
                            "dispute_category": dispute_category,
                        },
                        "priority": priority,
                        "automated": True,
                    })

                elif resolution_type == "verify_trial_and_refund_if_valid":
                    actions.append({
                        "action_type": "verify_and_refund_trial",
                        "action_data": {
                            "dispute_category": dispute_category,
                            "auto_approved": True,
                        },
                        "priority": priority,
                        "automated": True,
                    })

                elif resolution_type == "pause_retry_and_notify":
                    actions.append({
                        "action_type": "pause_payment_retries",
                        "action_data": {
                            "dispute_category": dispute_category,
                        },
                        "priority": priority,
                        "automated": True,
                    })

                elif resolution_type in ("adjust_charge", "explain_price_change_or_grandfather"):
                    actions.append({
                        "action_type": "review_charge_adjustment",
                        "action_data": {
                            "dispute_category": dispute_category,
                            "resolution_type": resolution_type,
                            "max_refund_percentage": dispute.get("max_refund_percentage", 0),
                        },
                        "priority": priority,
                        "automated": True,
                    })

            elif dispute_category != "unknown":
                # Not auto-resolvable but can provide context
                actions.append({
                    "action_type": "create_dispute_ticket",
                    "action_data": {
                        "dispute_category": dispute_category,
                        "evidence_required": dispute.get("evidence_required", False),
                        "priority": priority,
                    },
                    "priority": "high",
                    "automated": True,
                })

            # Handle anomaly-triggered actions
            if anomaly.get("anomaly_detected", False):
                actions.append({
                    "action_type": "flag_billing_anomaly",
                    "action_data": {
                        "anomaly_types": anomaly.get("anomaly_types", []),
                        "severity": anomaly.get("severity", "none"),
                    },
                    "priority": "high" if anomaly.get("severity") == "high" else "medium",
                    "automated": True,
                })

            return actions

        except Exception:
            logger.exception("billing_action_generation_failed")
            return []

    def generate_billing_context(
        self,
        dispute: Dict[str, Any],
        anomaly: Dict[str, Any],
    ) -> str:
        """Generate billing context prompt addition for the LLM.

        Args:
            dispute: Output from classify_dispute().
            anomaly: Output from detect_anomaly().

        Returns:
            Prompt string to append to generation system prompt.
        """
        try:
            parts: List[str] = []

            dispute_category = dispute.get("dispute_category", "unknown")
            if dispute_category != "unknown":
                auto_resolvable = dispute.get("auto_resolvable", False)
                parts.append(
                    f"The customer has a billing dispute classified as '{dispute_category.replace('_', ' ')}'. "
                    f"This is {'automatically resolvable' if auto_resolvable else 'requires manual review'}. "
                )
                if auto_resolvable:
                    resolution = dispute.get("resolution_type", "").replace("_", " ")
                    parts.append(
                        f"The resolution path is: {resolution}. "
                        f"Explain the resolution clearly and provide a timeline. "
                    )
                else:
                    parts.append(
                        "Acknowledge the concern and explain that a specialist will review. "
                        "Provide an expected timeline for resolution. "
                    )

            if anomaly.get("anomaly_detected", False):
                anomaly_types = ", ".join(anomaly.get("anomaly_types", []))
                parts.append(
                    f"A billing anomaly was detected: {anomaly_types}. "
                    f"This adds credibility to the customer's concern. "
                    f"Take their report seriously and provide immediate next steps."
                )

            return " ".join(parts) if parts else ""

        except Exception:
            return ""

    def generate_self_service_context(
        self,
        dispute: Dict[str, Any],
        anomaly: Dict[str, Any],
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Generate self-service billing portal context for the customer.

        Args:
            dispute: Output from classify_dispute().
            anomaly: Output from detect_anomaly().
            customer_tier: Customer subscription tier.

        Returns:
            Self-service context dict:
              - portal_url: str
              - available_actions: List[str]
              - dispute_status: str
              - refund_eligible: bool
        """
        try:
            dispute_category = dispute.get("dispute_category", "unknown")
            auto_resolvable = dispute.get("auto_resolvable", False)

            # Determine available actions based on dispute type
            actions = ["view_billing_history", "download_invoice"]
            if auto_resolvable:
                actions.extend(["request_refund", "dispute_charge"])
            if dispute_category in ("missing_refund", "double_charge"):
                actions.extend(["track_refund", "check_payment_status"])
            if customer_tier in ("growth", "enterprise"):
                actions.extend(["contact_billing_specialist", "schedule_callback"])

            # Refund eligibility
            refund_eligible = (
                auto_resolvable
                and dispute.get("max_refund_percentage", 0) > 0
                and dispute_category != "unknown"
            )

            # Dispute status
            if dispute_category == "unknown":
                status = "no_dispute"
            elif auto_resolvable:
                status = "auto_resolvable"
            else:
                status = "manual_review_required"

            return {
                "portal_url": "/billing/portal",
                "available_actions": actions,
                "dispute_status": status,
                "refund_eligible": refund_eligible,
            }
        except Exception:
            logger.exception("self_service_context_failed")
            return {
                "portal_url": "/billing/portal",
                "available_actions": ["view_billing_history"],
                "dispute_status": "unknown",
                "refund_eligible": False,
            }

    def auto_resolve_paddle_dispute(
        self,
        dispute: Dict[str, Any],
        anomaly: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate Paddle dispute auto-resolution data.

        Args:
            dispute: Output from classify_dispute().
            anomaly: Output from detect_anomaly().

        Returns:
            Paddle dispute dict:
              - dispute_id: str
              - auto_resolved: bool
              - resolution_action: str
              - refund_amount: Optional[float]
              - processing_time_hours: int
        """
        try:
            import uuid
            dispute_id = f"pad_{uuid.uuid4().hex[:10]}"

            auto_resolvable = dispute.get("auto_resolvable", False)
            resolution_type = dispute.get("resolution_type", "manual_review")
            max_refund_pct = dispute.get("max_refund_percentage", 0)

            auto_resolved = False
            resolution_action = "manual_review"
            refund_amount = None
            processing_hours = 48

            if auto_resolvable:
                auto_resolved = True
                if resolution_type == "refund_duplicate":
                    resolution_action = "auto_refund_duplicate"
                    refund_amount = None  # Will be determined by Paddle
                    processing_hours = 24
                elif resolution_type == "check_refund_status":
                    resolution_action = "check_refund_status_api"
                    processing_hours = 2
                elif resolution_type == "verify_trial_and_refund_if_valid":
                    resolution_action = "verify_trial_auto_refund"
                    processing_hours = 12
                elif resolution_type == "pause_retry_and_notify":
                    resolution_action = "pause_payment_retries"
                    processing_hours = 1
                elif resolution_type in ("adjust_charge", "explain_price_change_or_grandfather"):
                    resolution_action = "review_and_adjust"
                    processing_hours = 24

            # Anomaly speeds up resolution
            if anomaly.get("anomaly_detected", False) and anomaly.get("severity") == "high":
                processing_hours = max(1, processing_hours // 2)

            return {
                "dispute_id": dispute_id,
                "auto_resolved": auto_resolved,
                "resolution_action": resolution_action,
                "refund_amount": refund_amount,
                "processing_time_hours": processing_hours,
            }
        except Exception:
            logger.exception("paddle_dispute_resolution_failed")
            return {
                "dispute_id": "",
                "auto_resolved": False,
                "resolution_action": "manual_review",
                "refund_amount": None,
                "processing_time_hours": 48,
            }

    def _anomaly_recommendation(self, anomaly_types: List[str], severity: str) -> str:
        """Generate recommendation based on anomaly types."""
        if not anomaly_types:
            return "no_anomaly_detected_standard_flow"

        if "amount_deviation" in anomaly_types:
            if severity == "high":
                return "immediate_investigation_refund_likely"
            return "review_charge_explain_to_customer"

        if "unexpected_charge_reported" in anomaly_types:
            return "verify_charge_and_explain_or_refund"

        return "review_anomaly_and_resolve"

    def _default_dispute(self) -> Dict[str, Any]:
        """Return default dispute classification."""
        return {
            "dispute_category": "unknown",
            "auto_resolvable": False,
            "resolution_type": "manual_review",
            "priority": "medium",
            "evidence_required": False,
            "confidence": 0.0,
            "matched_keywords": [],
            "max_refund_percentage": 0,
        }
