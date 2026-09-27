"""
Churn Retention Engine — Churn Risk Scoring + Dynamic Retention + Win-Back.

Improvement Target: Cancellation/Retention 70% → 85% automation.

Components:
  1. Churn Risk Scorer: Multi-signal churn risk assessment based on
     customer signals, conversation patterns, account age, and intent.
     Produces a churn probability and risk tier.
  2. Dynamic Retention Offer Engine: ToT-branching decision tree that
     selects the optimal retention offer based on churn reason, customer
     value, and risk tier. Generates personalized offers automatically.
  3. Win-Back Automation: Post-cancellation re-engagement sequence
     that triggers automated win-back emails/offers at optimal intervals.

Architecture:
  Called from smart_enrichment node to assess churn risk and build
  retention context. Called from auto_action node to trigger retention
  actions (offers, emails, plan adjustments).

BC-001: company_id first parameter on public methods.
BC-008: Every method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("churn_retention")


# ══════════════════════════════════════════════════════════════════
# CHURN RISK SIGNALS
# ══════════════════════════════════════════════════════════════════

CANCELLATION_KEYWORDS: Dict[str, List[str]] = {
    "direct_cancel": [
        "cancel", "cancel my", "cancel the", "cancel subscription",
        "cancel my subscription", "cancel my account", "close my account",
        "delete my account", "want to cancel", "wish to cancel",
        "stop my subscription", "end my subscription", "discontinue",
        "unsubscribe", "opt out",
    ],
    "indirect_cancel": [
        "not worth", "too expensive", "cheaper alternative", "competitor",
        "switching to", "thinking about leaving", "considering canceling",
        "not using anymore", "don't need", "found something else",
        "better deal elsewhere", "not satisfied", "looking for alternatives",
    ],
    "price_sensitivity": [
        "too expensive", "cost too much", "overpriced", "can't afford",
        "budget", "cheaper", "discount", "free alternative",
        "price increase", "paying too much", "not worth the price",
    ],
    "feature_gap": [
        "missing feature", "doesn't have", "wish it could",
        "need something that", "limitation", "doesn't support",
        "not capable", "can't do", "workaround",
    ],
    "support_fatigue": [
        "still not fixed", "no resolution", "waste of time",
        "keep getting", "tired of", "support is useless",
        "no help", "getting nowhere", "runaround",
    ],
}

# Churn risk tiers
CHURN_RISK_TIERS: Dict[str, Dict[str, Any]] = {
    "low": {
        "probability_range": (0.0, 0.3),
        "retention_effort": "light",
        "offer_tier": "basic",
    },
    "medium": {
        "probability_range": (0.3, 0.6),
        "retention_effort": "moderate",
        "offer_tier": "enhanced",
    },
    "high": {
        "probability_range": (0.6, 0.85),
        "retention_effort": "strong",
        "offer_tier": "premium",
    },
    "critical": {
        "probability_range": (0.85, 1.0),
        "retention_effort": "maximum",
        "offer_tier": "executive",
    },
}

# Retention offer catalog
RETENTION_OFFERS: Dict[str, Dict[str, Any]] = {
    "plan_downgrade": {
        "description": "Offer a lower-cost plan that meets their needs",
        "effective_for": ["price_sensitivity"],
        "tier": "basic",
        "automation_level": "full",
    },
    "temporary_discount": {
        "description": "20-30% discount for 3 months",
        "effective_for": ["price_sensitivity", "indirect_cancel"],
        "tier": "enhanced",
        "automation_level": "full",
    },
    "feature_upgrade_no_cost": {
        "description": "Upgrade to next plan tier at current price for 6 months",
        "effective_for": ["feature_gap", "indirect_cancel"],
        "tier": "premium",
        "automation_level": "full",
    },
    "account_pause": {
        "description": "Pause subscription for 1-3 months instead of canceling",
        "effective_for": ["direct_cancel", "indirect_cancel"],
        "tier": "basic",
        "automation_level": "full",
    },
    "personalized_retention_call": {
        "description": "Schedule a call with retention specialist",
        "effective_for": ["support_fatigue", "feature_gap"],
        "tier": "executive",
        "automation_level": "partial",
    },
    "loyalty_credit": {
        "description": "One-time account credit as loyalty appreciation",
        "effective_for": ["indirect_cancel", "support_fatigue"],
        "tier": "enhanced",
        "automation_level": "full",
    },
    "extended_trial_of_premium": {
        "description": "30-day free trial of premium features",
        "effective_for": ["feature_gap"],
        "tier": "premium",
        "automation_level": "full",
    },
    "executive_review": {
        "description": "Senior team reviews account and creates custom retention plan",
        "effective_for": ["support_fatigue", "price_sensitivity", "feature_gap"],
        "tier": "executive",
        "automation_level": "partial",
    },
}

# Win-back sequence templates
WINBACK_SEQUENCES: Dict[str, Dict[str, Any]] = {
    "immediate": {
        "delay_days": 0,
        "channel": "email",
        "template": "cancellation_confirmation_with_offer",
        "offer": "temporary_discount",
    },
    "short_term": {
        "delay_days": 3,
        "channel": "email",
        "template": "we_miss_you_check_in",
        "offer": "feature_upgrade_no_cost",
    },
    "medium_term": {
        "delay_days": 14,
        "channel": "email",
        "template": "new_features_announcement",
        "offer": "extended_trial_of_premium",
    },
    "long_term": {
        "delay_days": 30,
        "channel": "email",
        "template": "special_comeback_offer",
        "offer": "loyalty_credit",
    },
}


class ChurnRetentionEngine:
    """Churn Retention Engine for cancellation/retention automation.

    Provides:
      - Churn risk scoring (multi-signal)
      - Dynamic retention offer selection (ToT branching)
      - Win-back automation sequencing

    Usage:
        engine = ChurnRetentionEngine()
        risk = engine.score_churn_risk(query, classification, signals)
        offers = engine.select_retention_offers(risk, customer_tier)
        winback = engine.generate_winback_sequence(risk)
    """

    def __init__(self) -> None:
        """Initialize the churn retention engine."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        try:
            for category, keywords in CANCELLATION_KEYWORDS.items():
                patterns = []
                for kw in keywords:
                    if " " in kw:
                        patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
                    else:
                        patterns.append(re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE))
                self._compiled_patterns[category] = patterns
        except Exception:
            logger.exception("churn_pattern_compilation_failed")

    def score_churn_risk(
        self,
        query: str,
        classification: Optional[Dict[str, Any]] = None,
        signals: Optional[Dict[str, Any]] = None,
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Score churn risk based on multiple signals.

        Args:
            query: Customer's raw message.
            classification: Classification result (intent, confidence).
            signals: Extracted signals (sentiment, frustration, etc.).
            customer_tier: Customer subscription tier.

        Returns:
            Churn risk assessment dict:
              - churn_probability: float (0.0-1.0)
              - risk_tier: str (low/medium/high/critical)
              - cancellation_signals: Dict[str, List[str]]
              - primary_reason: str
              - retention_urgency: str (low/medium/high/immediate)
              - customer_value: str (basic/standard/premium/enterprise)
        """
        try:
            if not query:
                return self._default_risk()

            query_lower = query.lower()

            # Detect cancellation signals
            detected_signals: Dict[str, List[str]] = {}
            for category, patterns in self._compiled_patterns.items():
                matches = []
                for pattern in patterns:
                    found = pattern.findall(query_lower)
                    if found:
                        matches.extend(found)
                if matches:
                    detected_signals[category] = matches

            # Calculate base churn probability
            base_probability = 0.1  # Start with 10% baseline

            # Direct cancel signals are strongest
            if "direct_cancel" in detected_signals:
                base_probability += 0.5

            # Indirect cancel signals
            if "indirect_cancel" in detected_signals:
                base_probability += 0.25

            # Price sensitivity
            if "price_sensitivity" in detected_signals:
                base_probability += 0.15

            # Feature gap
            if "feature_gap" in detected_signals:
                base_probability += 0.1

            # Support fatigue
            if "support_fatigue" in detected_signals:
                base_probability += 0.2

            # Factor in classification intent
            if classification:
                intent = classification.get("intent", "")
                if intent in ("cancellation", "cancel"):
                    base_probability += 0.3
                elif intent in ("complaint", "billing"):
                    base_probability += 0.1

            # Factor in signals
            if signals:
                frustration = signals.get("frustration_score", 0)
                if frustration > 70:
                    base_probability += 0.15
                sentiment = signals.get("sentiment", 0.5)
                if sentiment < 0.3:
                    base_probability += 0.1

            # Factor in customer tier (higher tier = more retention effort)
            tier_value = {
                "free": "basic",
                "starter": "standard",
                "growth": "premium",
                "enterprise": "enterprise",
            }

            # Cap at 1.0
            churn_probability = min(1.0, base_probability)

            # Determine risk tier
            risk_tier = "low"
            for tier_name, tier_config in CHURN_RISK_TIERS.items():
                low, high = tier_config["probability_range"]
                if low <= churn_probability < high:
                    risk_tier = tier_name
                    break
            if churn_probability >= 0.85:
                risk_tier = "critical"

            # Determine primary reason
            primary_reason = "general"
            reason_priority = ["direct_cancel", "price_sensitivity", "support_fatigue", "feature_gap", "indirect_cancel"]
            for reason in reason_priority:
                if reason in detected_signals:
                    primary_reason = reason
                    break

            # Determine retention urgency
            if churn_probability >= 0.7:
                urgency = "immediate"
            elif churn_probability >= 0.5:
                urgency = "high"
            elif churn_probability >= 0.3:
                urgency = "medium"
            else:
                urgency = "low"

            return {
                "churn_probability": round(churn_probability, 3),
                "risk_tier": risk_tier,
                "cancellation_signals": detected_signals,
                "primary_reason": primary_reason,
                "retention_urgency": urgency,
                "customer_value": tier_value.get(customer_tier, "basic"),
            }

        except Exception:
            logger.exception("churn_risk_scoring_failed")
            return self._default_risk()

    def select_retention_offers(
        self,
        churn_risk: Dict[str, Any],
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Select optimal retention offers using ToT-branching logic.

        Generates multiple offer branches (like Tree of Thoughts), evaluates
        which is most likely to succeed, and returns the ranked offers.

        Args:
            churn_risk: Output from score_churn_risk().
            customer_tier: Customer subscription tier.

        Returns:
            Retention offer dict:
              - recommended_offers: List[Dict] (ranked by effectiveness)
              - primary_offer: Dict (best offer)
              - contingency_offers: List[Dict] (if primary is declined)
              - prompt_addition: str (for LLM context)
        """
        try:
            primary_reason = churn_risk.get("primary_reason", "general")
            risk_tier = churn_risk.get("risk_tier", "low")
            customer_value = churn_risk.get("customer_value", "basic")

            # Find effective offers for the primary reason
            effective_offers: List[Dict[str, Any]] = []
            for offer_name, offer_config in RETENTION_OFFERS.items():
                if primary_reason in offer_config["effective_for"]:
                    # Score the offer based on tier match and automation level
                    tier_order = ["basic", "enhanced", "premium", "executive"]
                    offer_tier_idx = tier_order.index(offer_config["tier"]) if offer_config["tier"] in tier_order else 0
                    risk_tier_idx = tier_order.index(risk_tier) if risk_tier in tier_order else 0

                    # Better match if offer tier matches or exceeds risk tier
                    tier_match = 1.0 if offer_tier_idx >= risk_tier_idx else 0.5

                    # Prefer fully automated offers
                    automation_score = 1.0 if offer_config["automation_level"] == "full" else 0.7

                    # Higher value customers get premium offers
                    value_score = 1.0 if customer_value in ("premium", "enterprise") and offer_tier_idx >= 2 else 0.5

                    effectiveness = round((tier_match * 0.4 + automation_score * 0.35 + value_score * 0.25), 3)

                    effective_offers.append({
                        "offer_name": offer_name,
                        "description": offer_config["description"],
                        "effective_for": offer_config["effective_for"],
                        "tier": offer_config["tier"],
                        "automation_level": offer_config["automation_level"],
                        "effectiveness_score": effectiveness,
                    })

            # Sort by effectiveness
            effective_offers.sort(key=lambda x: x["effectiveness_score"], reverse=True)

            # If no offers matched, add default
            if not effective_offers:
                effective_offers.append({
                    "offer_name": "account_pause",
                    "description": "Pause subscription for 1-3 months instead of canceling",
                    "effective_for": ["direct_cancel"],
                    "tier": "basic",
                    "automation_level": "full",
                    "effectiveness_score": 0.5,
                })

            # Split into primary + contingency
            primary_offer = effective_offers[0] if effective_offers else {}
            contingency_offers = effective_offers[1:4] if len(effective_offers) > 1 else []

            # Generate prompt addition for LLM
            prompt_addition = self._generate_retention_prompt(churn_risk, primary_offer)

            return {
                "recommended_offers": effective_offers,
                "primary_offer": primary_offer,
                "contingency_offers": contingency_offers,
                "prompt_addition": prompt_addition,
            }

        except Exception:
            logger.exception("retention_offer_selection_failed")
            return {
                "recommended_offers": [],
                "primary_offer": {},
                "contingency_offers": [],
                "prompt_addition": "",
            }

    def generate_winback_sequence(
        self,
        churn_risk: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a win-back automation sequence for post-cancellation.

        Args:
            churn_risk: Output from score_churn_risk().

        Returns:
            Win-back sequence dict:
              - sequence: List[Dict] (ordered touchpoints)
              - total_duration_days: int
              - automated: bool
        """
        try:
            risk_tier = churn_risk.get("risk_tier", "low")
            primary_reason = churn_risk.get("primary_reason", "general")

            # Determine which win-back steps to include
            sequence: List[Dict[str, Any]] = []

            # Always include immediate confirmation with offer
            sequence.append({
                **WINBACK_SEQUENCES["immediate"],
                "reason_specific_offer": self._reason_to_offer(primary_reason),
            })

            # Add more steps based on risk tier
            if risk_tier in ("medium", "high", "critical"):
                sequence.append(WINBACK_SEQUENCES["short_term"])

            if risk_tier in ("high", "critical"):
                sequence.append(WINBACK_SEQUENCES["medium_term"])

            if risk_tier == "critical":
                sequence.append(WINBACK_SEQUENCES["long_term"])

            total_days = max(s.get("delay_days", 0) for s in sequence) if sequence else 0

            return {
                "sequence": sequence,
                "total_duration_days": total_days,
                "automated": True,
                "primary_reason": primary_reason,
            }

        except Exception:
            logger.exception("winback_sequence_generation_failed")
            return {
                "sequence": [],
                "total_duration_days": 0,
                "automated": False,
                "primary_reason": "unknown",
            }

    def get_retention_actions(
        self,
        churn_risk: Dict[str, Any],
        retention_offers: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get automated retention actions to execute.

        Args:
            churn_risk: Output from score_churn_risk().
            retention_offers: Output from select_retention_offers().

        Returns:
            List of action dicts for auto_action node.
        """
        try:
            actions: List[Dict[str, Any]] = []
            risk_tier = churn_risk.get("risk_tier", "low")
            primary_offer = retention_offers.get("primary_offer", {})

            if not primary_offer:
                return actions

            offer_name = primary_offer.get("offer_name", "")

            # Action: Apply retention offer
            if primary_offer.get("automation_level") == "full":
                actions.append({
                    "action_type": "apply_retention_offer",
                    "action_data": {
                        "offer_name": offer_name,
                        "description": primary_offer.get("description", ""),
                        "risk_tier": risk_tier,
                    },
                    "priority": "high" if risk_tier in ("high", "critical") else "medium",
                    "automated": True,
                })

            # Action: Schedule win-back sequence if customer proceeds to cancel
            if risk_tier in ("medium", "high", "critical"):
                actions.append({
                    "action_type": "schedule_winback",
                    "action_data": {
                        "risk_tier": risk_tier,
                        "primary_reason": churn_risk.get("primary_reason", "general"),
                    },
                    "priority": "medium",
                    "automated": True,
                })

            # Action: Flag for retention specialist if partial automation
            if primary_offer.get("automation_level") == "partial":
                actions.append({
                    "action_type": "flag_for_retention_specialist",
                    "action_data": {
                        "offer_name": offer_name,
                        "churn_probability": churn_risk.get("churn_probability", 0.0),
                        "customer_value": churn_risk.get("customer_value", "basic"),
                    },
                    "priority": "high",
                    "automated": True,
                })

            return actions

        except Exception:
            logger.exception("retention_action_generation_failed")
            return []

    def negotiate_retention(
        self,
        churn_risk: Dict[str, Any],
        retention_offers: Dict[str, Any],
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Generate retention negotiation strategy with acceptance likelihood.

        Args:
            churn_risk: Output from score_churn_risk().
            retention_offers: Output from select_retention_offers().
            customer_tier: Customer subscription tier.

        Returns:
            Retention negotiation dict:
              - negotiation_strategy: str
              - offer_presented: str
              - counter_offers: List[str]
              - acceptance_likelihood: float
              - negotiation_stage: str
        """
        try:
            primary_offer = retention_offers.get("primary_offer", {})
            contingency = retention_offers.get("contingency_offers", [])
            probability = churn_risk.get("churn_probability", 0.1)

            # Determine negotiation strategy based on risk
            if probability >= 0.7:
                strategy = "aggressive_retention"
                stage = "critical_intervention"
            elif probability >= 0.4:
                strategy = "empathetic_retention"
                stage = "active_negotiation"
            else:
                strategy = "soft_retention"
                stage = "initial_engagement"

            offer_name = primary_offer.get("offer_name", "account_pause")
            counter_offers = [c.get("offer_name", "") for c in contingency[:3]]

            # Estimate acceptance likelihood
            base_likelihood = 1.0 - probability  # Inverse of churn probability
            automation_bonus = 0.1 if primary_offer.get("automation_level") == "full" else 0.0
            tier_bonus = 0.05 if customer_tier in ("growth", "enterprise") else 0.0
            acceptance_likelihood = min(0.95, base_likelihood + automation_bonus + tier_bonus)

            return {
                "negotiation_strategy": strategy,
                "offer_presented": offer_name,
                "counter_offers": counter_offers,
                "acceptance_likelihood": round(acceptance_likelihood, 3),
                "negotiation_stage": stage,
            }
        except Exception:
            logger.exception("retention_negotiation_failed")
            return {
                "negotiation_strategy": "soft_retention",
                "offer_presented": "account_pause",
                "counter_offers": [],
                "acceptance_likelihood": 0.0,
                "negotiation_stage": "unknown",
            }

    def generate_winback_automation(
        self,
        churn_risk: Dict[str, Any],
        retention_offers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate automated win-back sequence data for post-cancellation.

        Args:
            churn_risk: Output from score_churn_risk().
            retention_offers: Output from select_retention_offers().

        Returns:
            Win-back automation dict:
              - sequence_active: bool
              - sequence_steps: List[Dict]
              - total_duration_days: int
              - primary_offer: str
        """
        try:
            risk_tier = churn_risk.get("risk_tier", "low")
            primary_offer = retention_offers.get("primary_offer", {})

            sequence_active = risk_tier in ("medium", "high", "critical")

            # Build sequence steps
            steps = []
            if sequence_active:
                steps.append({
                    "delay_days": 0,
                    "action": "send_cancellation_confirmation",
                    "channel": "email",
                    "include_offer": True,
                })
                if risk_tier in ("high", "critical"):
                    steps.append({
                        "delay_days": 3,
                        "action": "send_we_miss_you",
                        "channel": "email",
                        "include_offer": True,
                    })
                if risk_tier == "critical":
                    steps.append({
                        "delay_days": 14,
                        "action": "send_comeback_offer",
                        "channel": "email",
                        "include_offer": True,
                    })
                    steps.append({
                        "delay_days": 30,
                        "action": "send_final_offer",
                        "channel": "email",
                        "include_offer": True,
                    })

            total_days = max(s.get("delay_days", 0) for s in steps) if steps else 0

            return {
                "sequence_active": sequence_active,
                "sequence_steps": steps,
                "total_duration_days": total_days,
                "primary_offer": primary_offer.get("offer_name", ""),
            }
        except Exception:
            logger.exception("winback_automation_failed")
            return {
                "sequence_active": False,
                "sequence_steps": [],
                "total_duration_days": 0,
                "primary_offer": "",
            }

    def _generate_retention_prompt(
        self,
        churn_risk: Dict[str, Any],
        primary_offer: Dict[str, Any],
    ) -> str:
        """Generate prompt addition for LLM retention context."""
        try:
            probability = churn_risk.get("churn_probability", 0.0)
            reason = churn_risk.get("primary_reason", "general")
            offer = primary_offer.get("offer_name", "account_pause")
            offer_desc = primary_offer.get("description", "")

            prompt = (
                f"The customer has a {probability:.0%} churn probability, "
                f"primarily due to {reason.replace('_', ' ')}. "
                f"The recommended retention offer is: {offer} ({offer_desc}). "
                f"Present this offer naturally in your response as a genuine "
                f"alternative to cancellation. Be empathetic but not pushy. "
                f"Give the customer space to decide while clearly showing the value."
            )

            return prompt

        except Exception:
            return ""

    def _reason_to_offer(self, reason: str) -> str:
        """Map a churn reason to the best win-back offer."""
        reason_offer_map = {
            "price_sensitivity": "temporary_discount",
            "feature_gap": "extended_trial_of_premium",
            "support_fatigue": "personalized_retention_call",
            "direct_cancel": "account_pause",
            "indirect_cancel": "loyalty_credit",
        }
        return reason_offer_map.get(reason, "temporary_discount")

    def _default_risk(self) -> Dict[str, Any]:
        """Return default low-risk churn assessment."""
        return {
            "churn_probability": 0.1,
            "risk_tier": "low",
            "cancellation_signals": {},
            "primary_reason": "general",
            "retention_urgency": "low",
            "customer_value": "basic",
        }
